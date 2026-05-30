import tempfile
import unittest
from pathlib import Path

from services.saas.credits import CreditLedger
from services.saas.db import connect_database, initialize_database
from services.saas.jobs import JobStore
from services.saas.pipeline import PipelineError, PipelineMetadata, PipelineResult
from services.saas.worker import SingleJobWorker


class FakePipeline:
    def __init__(
        self,
        *,
        duration_seconds: int = 600,
        result: PipelineResult | None = None,
        error_code: str | None = None,
        metadata_error_code: str | None = None,
    ):
        self.duration_seconds = duration_seconds
        self.result = result or PipelineResult(
            source_srt_path="/tmp/jobs/job/source.srt",
            translated_srt_path="/tmp/jobs/job/translated.srt",
            finalized_srt_path="/tmp/results/job/finalized.srt",
        )
        self.error_code = error_code
        self.metadata_error_code = metadata_error_code
        self.metadata_calls = 0
        self.run_calls = 0

    def fetch_metadata(self, source_url: str) -> PipelineMetadata:
        self.metadata_calls += 1
        if self.metadata_error_code:
            raise PipelineError(self.metadata_error_code, "fake metadata failed")
        return PipelineMetadata(
            video_title="demo video",
            video_duration_seconds=self.duration_seconds,
        )

    def run(self, *, job_id: str, source_url: str) -> PipelineResult:
        self.run_calls += 1
        if self.error_code:
            raise PipelineError(self.error_code, "fake pipeline failed")
        return self.result


class SaasWorkerTests(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect_database(Path(tmp.name) / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        conn.execute(
            """
            INSERT INTO users (id, email, role, status, created_at, updated_at)
            VALUES ('user_1', 'member@example.com', 'member', 'active',
                    '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.commit()
        return conn

    def _setup_with_root(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        conn = connect_database(root / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        conn.execute(
            """
            INSERT INTO users (id, email, role, status, created_at, updated_at)
            VALUES ('user_1', 'member@example.com', 'member', 'active',
                    '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """
        )
        conn.commit()
        return conn, root

    def _create_job(
        self,
        conn,
        *,
        job_type: str = "paid",
        source_url: str = "https://example.com/video",
    ) -> str:
        return JobStore(conn).create_job(
            user_id="user_1",
            source_url=source_url,
            now="2026-01-01T00:00:00Z",
            job_type=job_type,
        )

    def _grant(self, conn, minutes: float) -> None:
        CreditLedger(conn).grant(
            user_id="user_1",
            minutes=minutes,
            reason="test grant",
            idempotency_key=f"grant-{minutes}",
            created_at="2026-01-01T00:00:00Z",
        )

    def test_worker_success_reserves_consumes_and_stores_outputs(self):
        conn = self._setup()
        job_id = self._create_job(conn)
        self._grant(conn, 30)
        pipeline = FakePipeline(duration_seconds=600)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"]
            for row in conn.execute(
                "SELECT type FROM credit_ledger ORDER BY rowid"
            )
        ]
        event_codes = [
            row["code"]
            for row in conn.execute(
                "SELECT code FROM job_events WHERE job_id = ? ORDER BY created_at",
                (job_id,),
            )
        ]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 1)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["stage"], "cleanup_completed")
        self.assertEqual(job["video_duration_seconds"], 600)
        self.assertEqual(job["reserved_minutes"], 10)
        self.assertEqual(job["consumed_minutes"], 10)
        self.assertEqual(job["source_srt_path"], "/tmp/jobs/job/source.srt")
        self.assertEqual(job["translated_srt_path"], "/tmp/jobs/job/translated.srt")
        self.assertEqual(job["result_srt_path"], "/tmp/results/job/finalized.srt")
        self.assertEqual(ledger_types, ["grant", "reserve", "consume"])
        self.assertIn("metadata_fetched", event_codes)
        self.assertIn("job_succeeded", event_codes)

    def test_worker_success_cleans_temporary_media_when_job_data_dir_is_set(self):
        conn, root = self._setup_with_root()
        job_id = self._create_job(conn)
        self._grant(conn, 30)
        job_dir = root / "jobs" / job_id
        for path in [
            job_dir / "input" / "video.mp4",
            job_dir / "media" / "audio.opus",
            job_dir / "media" / "frames" / "001.jpg",
            job_dir / "media" / "chunks" / "chunk-001.opus",
            job_dir / "output" / "source.srt",
            job_dir / "output" / "translated.srt",
            job_dir / "cache" / "pre_pass.json",
            job_dir / "job.log",
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("data", encoding="utf-8")
        pipeline = FakePipeline(
            duration_seconds=600,
            result=PipelineResult(
                source_srt_path=str(job_dir / "output" / "source.srt"),
                translated_srt_path=str(job_dir / "output" / "translated.srt"),
                finalized_srt_path=str(root / "results" / job_id / "finalized.srt"),
            ),
        )

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
            job_data_dir=root / "jobs",
        ).run_once(now="2026-01-01T00:01:00Z")

        self.assertTrue(processed)
        self.assertFalse((job_dir / "input" / "video.mp4").exists())
        self.assertFalse((job_dir / "media" / "audio.opus").exists())
        self.assertFalse((job_dir / "media" / "frames" / "001.jpg").exists())
        self.assertFalse((job_dir / "media" / "chunks" / "chunk-001.opus").exists())
        self.assertTrue((job_dir / "output" / "source.srt").exists())
        self.assertTrue((job_dir / "output" / "translated.srt").exists())
        self.assertTrue((job_dir / "cache" / "pre_pass.json").exists())
        self.assertTrue((job_dir / "job.log").exists())

    def test_worker_fails_before_pipeline_when_credits_are_insufficient(self):
        conn = self._setup()
        job_id = self._create_job(conn)
        self._grant(conn, 5)
        pipeline = FakePipeline(duration_seconds=600)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"] for row in conn.execute("SELECT type FROM credit_ledger")
        ]
        balance = conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = 'user_1'"
        ).fetchone()["balance_minutes"]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 0)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["stage"], "metadata_fetched")
        self.assertEqual(job["error_code"], "INSUFFICIENT_CREDITS")
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(ledger_types, ["grant"])
        self.assertEqual(balance, 5)

    def test_worker_rejects_private_url_before_metadata_fetch(self):
        conn = self._setup()
        job_id = self._create_job(conn, source_url="http://127.0.0.1:9000/video")
        self._grant(conn, 30)
        pipeline = FakePipeline(duration_seconds=60)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"] for row in conn.execute("SELECT type FROM credit_ledger")
        ]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 0)
        self.assertEqual(pipeline.run_calls, 0)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "FORBIDDEN_URL")
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(ledger_types, ["grant"])

    def test_worker_marks_failed_when_metadata_fetch_fails(self):
        conn = self._setup()
        job_id = self._create_job(conn)
        self._grant(conn, 30)
        pipeline = FakePipeline(metadata_error_code="METADATA_FAILED")

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"] for row in conn.execute("SELECT type FROM credit_ledger")
        ]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 0)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["stage"], "created")
        self.assertEqual(job["error_code"], "METADATA_FAILED")
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(ledger_types, ["grant"])

    def test_worker_rejects_paid_job_over_max_duration_before_pipeline_run(self):
        conn = self._setup()
        job_id = self._create_job(conn)
        self._grant(conn, 120)
        pipeline = FakePipeline(duration_seconds=61)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
            max_video_duration_seconds=60,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"] for row in conn.execute("SELECT type FROM credit_ledger")
        ]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 0)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["stage"], "metadata_fetched")
        self.assertEqual(job["error_code"], "VIDEO_TOO_LONG")
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(ledger_types, ["grant"])

    def test_worker_runs_short_trial_job_without_credit_balance(self):
        conn = self._setup()
        job_id = self._create_job(conn, job_type="trial")
        pipeline = FakePipeline(duration_seconds=60)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_count = conn.execute("SELECT COUNT(*) FROM credit_ledger").fetchone()[0]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 1)
        self.assertEqual(job["status"], "succeeded")
        self.assertEqual(job["job_type"], "trial")
        self.assertEqual(job["video_duration_seconds"], 60)
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(job["consumed_minutes"], 0)
        self.assertEqual(ledger_count, 0)

    def test_worker_rejects_long_trial_job_before_pipeline_run(self):
        conn = self._setup()
        job_id = self._create_job(conn, job_type="trial")
        pipeline = FakePipeline(duration_seconds=61)

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_count = conn.execute("SELECT COUNT(*) FROM credit_ledger").fetchone()[0]

        self.assertTrue(processed)
        self.assertEqual(pipeline.metadata_calls, 1)
        self.assertEqual(pipeline.run_calls, 0)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["stage"], "metadata_fetched")
        self.assertEqual(job["error_code"], "TRIAL_VIDEO_TOO_LONG")
        self.assertEqual(job["reserved_minutes"], 0)
        self.assertEqual(job["consumed_minutes"], 0)
        self.assertEqual(ledger_count, 0)

    def test_worker_refunds_reserved_credits_when_pipeline_fails(self):
        conn = self._setup()
        job_id = self._create_job(conn)
        self._grant(conn, 30)
        pipeline = FakePipeline(duration_seconds=600, error_code="GEMINI_FAILED")

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        ledger_types = [
            row["type"]
            for row in conn.execute(
                "SELECT type FROM credit_ledger ORDER BY rowid"
            )
        ]
        balance = conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = 'user_1'"
        ).fetchone()["balance_minutes"]

        self.assertTrue(processed)
        self.assertEqual(pipeline.run_calls, 1)
        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["error_code"], "GEMINI_FAILED")
        self.assertEqual(job["reserved_minutes"], 10)
        self.assertEqual(job["consumed_minutes"], 0)
        self.assertEqual(ledger_types, ["grant", "reserve", "refund"])
        self.assertEqual(balance, 30)

    def test_worker_returns_false_when_no_job_is_queued(self):
        conn = self._setup()
        pipeline = FakePipeline()

        processed = SingleJobWorker(
            conn,
            worker_id="worker-1",
            pipeline=pipeline,
        ).run_once(now="2026-01-01T00:01:00Z")

        self.assertFalse(processed)
        self.assertEqual(pipeline.metadata_calls, 0)
        self.assertEqual(pipeline.run_calls, 0)


if __name__ == "__main__":
    unittest.main()
