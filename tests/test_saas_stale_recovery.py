import tempfile
import unittest
from pathlib import Path

from services.saas.db import connect_database, initialize_database
from services.saas.jobs import JobStore


class SaasStaleRecoveryTests(unittest.TestCase):
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

    def _create_running_job(self, conn, *, heartbeat_at: str) -> str:
        job_id = JobStore(conn).create_job(
            user_id="user_1",
            source_url="https://example.com/video",
            now="2026-01-01T00:00:00Z",
        )
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                worker_id = 'worker-old',
                heartbeat_at = ?,
                started_at = '2026-01-01T00:01:00Z',
                progress_message = 'running'
            WHERE id = ?
            """,
            (heartbeat_at, job_id),
        )
        conn.commit()
        return job_id

    def test_recover_stale_running_jobs_requeues_old_heartbeat_and_writes_event(self):
        conn = self._setup()
        job_id = self._create_running_job(
            conn,
            heartbeat_at="2026-01-01T00:00:00Z",
        )

        recovered = JobStore(conn).recover_stale_running_jobs(
            now="2026-01-01T00:03:00Z",
            heartbeat_timeout_seconds=120,
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        event = conn.execute(
            "SELECT * FROM job_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        self.assertEqual(recovered, [job_id])
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["worker_id"], None)
        self.assertEqual(job["heartbeat_at"], None)
        self.assertEqual(job["started_at"], None)
        self.assertEqual(job["retry_count"], 1)
        self.assertEqual(event["code"], "stale_running_requeued")

    def test_recover_stale_running_jobs_keeps_recent_heartbeat_running(self):
        conn = self._setup()
        job_id = self._create_running_job(
            conn,
            heartbeat_at="2026-01-01T00:02:30Z",
        )

        recovered = JobStore(conn).recover_stale_running_jobs(
            now="2026-01-01T00:03:00Z",
            heartbeat_timeout_seconds=120,
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        self.assertEqual(recovered, [])
        self.assertEqual(job["status"], "running")
        self.assertEqual(job["worker_id"], "worker-old")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_events").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
