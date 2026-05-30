import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.saas.credits import CreditLedger, InsufficientCredits
from services.saas.db import connect_database, initialize_database
from services.saas.jobs import JobStore
from services.saas.state import (
    JobStage,
    JobStatus,
    assert_stage_transition,
    assert_status_transition,
)


class SaasPhase1FoundationTests(unittest.TestCase):
    def _connect(self) -> sqlite3.Connection:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "app.db"
        conn = connect_database(db_path)
        self.addCleanup(conn.close)
        initialize_database(conn)
        return conn

    def _create_user(self, conn: sqlite3.Connection, user_id: str = "user_1") -> str:
        conn.execute(
            """
            INSERT INTO users (id, email, role, status, created_at, updated_at)
            VALUES (?, ?, 'member', 'active', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (user_id, f"{user_id}@example.com"),
        )
        conn.commit()
        return user_id

    def test_schema_initialization_enables_wal_and_creates_required_tables(self):
        conn = self._connect()

        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertEqual(foreign_keys, 1)
        self.assertTrue(
            {
                "users",
                "invite_codes",
                "sessions",
                "jobs",
                "job_events",
                "credit_balances",
                "credit_ledger",
                "admin_audit_logs",
            }.issubset(tables)
        )

    def test_initialize_database_migrates_existing_jobs_table_without_job_type(self):
        conn = self._connect()
        conn.execute("DROP TABLE jobs")
        conn.execute(
            """
            CREATE TABLE jobs (
              id TEXT PRIMARY KEY,
              user_id TEXT NOT NULL REFERENCES users(id),
              source_url TEXT NOT NULL,
              source_url_redacted TEXT NOT NULL,
              status TEXT NOT NULL,
              stage TEXT NOT NULL,
              current_chunk_index INTEGER NOT NULL DEFAULT 0,
              total_chunks INTEGER NOT NULL DEFAULT 0,
              progress_message TEXT,
              error_code TEXT,
              error_message TEXT,
              video_title TEXT,
              video_duration_seconds INTEGER,
              reserved_minutes REAL NOT NULL DEFAULT 0,
              consumed_minutes REAL NOT NULL DEFAULT 0,
              worker_id TEXT,
              heartbeat_at TEXT,
              source_srt_path TEXT,
              translated_srt_path TEXT,
              result_srt_path TEXT,
              log_path TEXT,
              retry_count INTEGER NOT NULL DEFAULT 0,
              retry_after_seconds INTEGER,
              created_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              expires_at TEXT
            )
            """
        )
        conn.commit()

        initialize_database(conn)

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
        self.assertIn("job_type", columns)
        job_id = JobStore(conn).create_job(
            user_id=self._create_user(conn),
            source_url="https://example.com/video",
            now="2026-01-01T00:00:00Z",
        )
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(job["job_type"], "paid")

    def test_status_and_stage_transitions_reject_invalid_paths(self):
        assert_status_transition(JobStatus.QUEUED, JobStatus.RUNNING)
        assert_status_transition(JobStatus.RUNNING, JobStatus.SUCCEEDED)
        assert_status_transition(JobStatus.RUNNING, JobStatus.RETRYING)
        assert_status_transition(JobStatus.RETRYING, JobStatus.RUNNING)

        with self.assertRaises(ValueError):
            assert_status_transition(JobStatus.FAILED, JobStatus.SUCCEEDED)

        assert_stage_transition(JobStage.CREATED, JobStage.METADATA_FETCHED)

        with self.assertRaises(ValueError):
            assert_stage_transition(JobStage.CREATED, JobStage.VIDEO_DOWNLOADED)

    def test_credit_ledger_grant_reserve_consume_and_refund_are_transactional(self):
        conn = self._connect()
        user_id = self._create_user(conn)
        ledger = CreditLedger(conn)
        job_store = JobStore(conn)
        job_id = job_store.create_job(
            user_id=user_id,
            source_url="https://example.com/video",
            now="2026-01-01T00:00:00Z",
        )

        self.assertEqual(
            ledger.grant(
                user_id=user_id,
                minutes=30,
                reason="initial grant",
                idempotency_key="grant-user-1",
                created_at="2026-01-01T00:00:00Z",
            ),
            30,
        )
        self.assertEqual(
            ledger.reserve(
                user_id=user_id,
                job_id=job_id,
                minutes=10,
                idempotency_key="reserve-job-1",
                created_at="2026-01-01T00:01:00Z",
            ),
            20,
        )
        self.assertEqual(
            ledger.consume(
                user_id=user_id,
                job_id=job_id,
                minutes=10,
                idempotency_key="consume-job-1",
                created_at="2026-01-01T00:02:00Z",
            ),
            20,
        )
        self.assertEqual(
            ledger.refund(
                user_id=user_id,
                job_id=job_id,
                minutes=4,
                idempotency_key="refund-job-1",
                created_at="2026-01-01T00:03:00Z",
            ),
            24,
        )

        rows = conn.execute(
            "SELECT type, minutes FROM credit_ledger ORDER BY created_at"
        ).fetchall()
        self.assertEqual(
            [(row["type"], row["minutes"]) for row in rows],
            [("grant", 30), ("reserve", 10), ("consume", 10), ("refund", 4)],
        )

        with self.assertRaises(InsufficientCredits):
            ledger.reserve(
                user_id=user_id,
                job_id=job_id,
                minutes=100,
                idempotency_key="reserve-too-much",
                created_at="2026-01-01T00:04:00Z",
            )

        balance = conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = ?",
            (user_id,),
        ).fetchone()["balance_minutes"]
        self.assertEqual(balance, 24)

    def test_credit_ledger_idempotency_key_replay_is_noop(self):
        conn = self._connect()
        user_id = self._create_user(conn)
        ledger = CreditLedger(conn)
        job_id = JobStore(conn).create_job(
            user_id=user_id,
            source_url="https://example.com/video",
            now="2026-01-01T00:00:00Z",
        )

        self.assertEqual(
            ledger.grant(
                user_id=user_id,
                minutes=30,
                reason="initial grant",
                idempotency_key="grant-idempotent",
                created_at="2026-01-01T00:00:00Z",
            ),
            30,
        )
        self.assertEqual(
            ledger.grant(
                user_id=user_id,
                minutes=30,
                reason="initial grant replay",
                idempotency_key="grant-idempotent",
                created_at="2026-01-01T00:00:01Z",
            ),
            30,
        )
        self.assertEqual(
            ledger.reserve(
                user_id=user_id,
                job_id=job_id,
                minutes=10,
                idempotency_key="reserve-idempotent",
                created_at="2026-01-01T00:01:00Z",
            ),
            20,
        )
        self.assertEqual(
            ledger.reserve(
                user_id=user_id,
                job_id=job_id,
                minutes=10,
                idempotency_key="reserve-idempotent",
                created_at="2026-01-01T00:01:01Z",
            ),
            20,
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM credit_ledger").fetchone()[0],
            2,
        )
        self.assertEqual(job["reserved_minutes"], 10)

    def test_credit_ledger_rejects_conflicting_idempotency_key_reuse(self):
        conn = self._connect()
        user_id = self._create_user(conn)
        ledger = CreditLedger(conn)

        ledger.grant(
            user_id=user_id,
            minutes=30,
            reason="initial grant",
            idempotency_key="grant-conflict",
            created_at="2026-01-01T00:00:00Z",
        )

        with self.assertRaises(ValueError):
            ledger.grant(
                user_id=user_id,
                minutes=31,
                reason="different amount",
                idempotency_key="grant-conflict",
                created_at="2026-01-01T00:00:01Z",
            )

        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM credit_ledger").fetchone()[0],
            1,
        )

    def test_claim_next_job_claims_exactly_one_queued_job(self):
        conn = self._connect()
        user_id = self._create_user(conn)
        job_store = JobStore(conn)
        job_id = job_store.create_job(
            user_id=user_id,
            source_url="https://example.com/video?token=secret",
            now="2026-01-01T00:00:00Z",
        )

        claimed = job_store.claim_next(
            worker_id="worker-1",
            now="2026-01-01T00:01:00Z",
        )
        second_claim = job_store.claim_next(
            worker_id="worker-2",
            now="2026-01-01T00:02:00Z",
        )
        stored = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["id"], job_id)
        self.assertIsNone(second_claim)
        self.assertEqual(stored["status"], "running")
        self.assertEqual(stored["stage"], "created")
        self.assertEqual(stored["worker_id"], "worker-1")
        self.assertEqual(stored["heartbeat_at"], "2026-01-01T00:01:00Z")
        self.assertEqual(stored["started_at"], "2026-01-01T00:01:00Z")
        self.assertEqual(stored["source_url_redacted"], "https://example.com/video")


if __name__ == "__main__":
    unittest.main()
