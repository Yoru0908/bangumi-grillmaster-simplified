import tempfile
import unittest
from pathlib import Path

from services.saas.cleanup import CleanupService
from services.saas.db import connect_database, initialize_database
from services.saas.jobs import JobStore


class SaasCleanupTests(unittest.TestCase):
    def _setup(self):
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

    def _create_job(self, conn, root: Path, *, status: str, created_at: str) -> str:
        job_id = JobStore(conn).create_job(
            user_id="user_1",
            source_url="https://example.com/video",
            now=created_at,
        )
        job_dir = root / "jobs" / job_id
        result_dir = root / "results" / job_id
        for path in [
            job_dir / "input" / "video.mp4",
            job_dir / "media" / "audio.opus",
            job_dir / "media" / "frames" / "001.jpg",
            job_dir / "media" / "chunks" / "chunk-001.opus",
            job_dir / "output" / "source.srt",
            job_dir / "output" / "translated.srt",
            job_dir / "cache" / "pre_pass.json",
            job_dir / "job.log",
            result_dir / "finalized.srt",
        ]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("data", encoding="utf-8")
        conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                stage = 'finalized',
                source_srt_path = ?,
                translated_srt_path = ?,
                result_srt_path = ?,
                log_path = ?,
                finished_at = '2026-01-01T01:00:00Z',
                expires_at = '2026-01-15T00:00:00Z'
            WHERE id = ?
            """,
            (
                status,
                str(job_dir / "output" / "source.srt"),
                str(job_dir / "output" / "translated.srt"),
                str(result_dir / "finalized.srt"),
                str(job_dir / "job.log"),
                job_id,
            ),
        )
        conn.commit()
        return job_id

    def test_success_cleanup_deletes_media_but_keeps_srt_cache_and_log(self):
        conn, root = self._setup()
        job_id = self._create_job(
            conn,
            root,
            status="succeeded",
            created_at="2026-01-01T00:00:00Z",
        )

        CleanupService(conn).cleanup_successful_job(
            job_id,
            job_data_dir=root / "jobs",
            now="2026-01-01T02:00:00Z",
        )

        job_dir = root / "jobs" / job_id
        self.assertFalse((job_dir / "input" / "video.mp4").exists())
        self.assertFalse((job_dir / "media" / "audio.opus").exists())
        self.assertFalse((job_dir / "media" / "frames" / "001.jpg").exists())
        self.assertFalse((job_dir / "media" / "chunks" / "chunk-001.opus").exists())
        self.assertTrue((job_dir / "output" / "source.srt").exists())
        self.assertTrue((job_dir / "output" / "translated.srt").exists())
        self.assertTrue((job_dir / "cache" / "pre_pass.json").exists())
        self.assertTrue((job_dir / "job.log").exists())
        self.assertEqual(
            conn.execute("SELECT stage FROM jobs WHERE id = ?", (job_id,)).fetchone()[
                "stage"
            ],
            "cleanup_completed",
        )

    def test_expired_result_cleanup_deletes_all_downloadable_srt_and_marks_expired(self):
        conn, root = self._setup()
        job_id = self._create_job(
            conn,
            root,
            status="succeeded",
            created_at="2026-01-01T00:00:00Z",
        )

        CleanupService(conn).cleanup_expired_results(now="2026-01-16T00:00:00Z")

        self.assertFalse((root / "jobs" / job_id / "output" / "source.srt").exists())
        self.assertFalse((root / "jobs" / job_id / "output" / "translated.srt").exists())
        self.assertFalse((root / "results" / job_id / "finalized.srt").exists())
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(job["status"], "expired")
        self.assertIsNone(job["source_srt_path"])
        self.assertIsNone(job["translated_srt_path"])
        self.assertIsNone(job["result_srt_path"])

    def test_failed_old_cleanup_deletes_entire_job_directory_after_ttl(self):
        conn, root = self._setup()
        job_id = self._create_job(
            conn,
            root,
            status="failed",
            created_at="2026-01-01T00:00:00Z",
        )
        conn.execute(
            "UPDATE jobs SET finished_at = '2026-01-01T01:00:00Z' WHERE id = ?",
            (job_id,),
        )
        conn.commit()

        CleanupService(conn).cleanup_failed_old_jobs(
            job_data_dir=root / "jobs",
            now="2026-01-03T00:00:00Z",
            ttl_hours=24,
        )

        self.assertFalse((root / "jobs" / job_id).exists())
        event = conn.execute(
            "SELECT * FROM job_events WHERE job_id = ? AND code = 'failed_tmp_cleaned'",
            (job_id,),
        ).fetchone()
        self.assertIsNotNone(event)

    def test_failed_recent_cleanup_keeps_directory_before_ttl(self):
        conn, root = self._setup()
        job_id = self._create_job(
            conn,
            root,
            status="failed",
            created_at="2026-01-01T00:00:00Z",
        )
        conn.execute(
            "UPDATE jobs SET finished_at = '2026-01-02T12:00:00Z' WHERE id = ?",
            (job_id,),
        )
        conn.commit()

        CleanupService(conn).cleanup_failed_old_jobs(
            job_data_dir=root / "jobs",
            now="2026-01-03T00:00:00Z",
            ttl_hours=24,
        )

        self.assertTrue((root / "jobs" / job_id).exists())


if __name__ == "__main__":
    unittest.main()
