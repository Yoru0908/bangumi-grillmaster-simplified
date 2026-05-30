import tempfile
import unittest
from pathlib import Path

from services.saas.db import connect_database, initialize_database
from services.saas.job_access import (
    ForbiddenJobAccess,
    InvalidJobArtifact,
    JobAccessService,
    JobNotFound,
)
from services.saas.jobs import JobStore


class SaasJobAccessTests(unittest.TestCase):
    def _setup_service(self) -> tuple[JobAccessService, object]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect_database(Path(tmp.name) / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        return JobAccessService(conn), conn

    def _create_user(
        self,
        conn,
        user_id: str,
        email: str,
        role: str = "member",
    ) -> str:
        conn.execute(
            """
            INSERT INTO users (id, email, role, status, created_at, updated_at)
            VALUES (?, ?, ?, 'active', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')
            """,
            (user_id, email, role),
        )
        conn.commit()
        return user_id

    def _create_job(self, conn, user_id: str, url: str, created_at: str) -> str:
        return JobStore(conn).create_job(
            user_id=user_id,
            source_url=url,
            now=created_at,
        )

    def _mark_outputs(self, conn, job_id: str) -> None:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'succeeded',
                stage = 'cleanup_completed',
                source_srt_path = '/tmp/jobs/job/source.srt',
                translated_srt_path = '/tmp/jobs/job/translated.srt',
                result_srt_path = '/tmp/results/job/finalized.srt'
            WHERE id = ?
            """,
            (job_id,),
        )
        conn.commit()

    def test_member_lists_only_own_jobs_and_admin_lists_all_jobs(self):
        service, conn = self._setup_service()
        self._create_user(conn, "user_1", "one@example.com")
        self._create_user(conn, "user_2", "two@example.com")
        self._create_user(conn, "admin_1", "admin@example.com", role="admin")
        first = self._create_job(
            conn,
            "user_1",
            "https://example.com/one?token=secret",
            "2026-01-01T00:00:00Z",
        )
        second = self._create_job(
            conn,
            "user_2",
            "https://example.com/two",
            "2026-01-01T00:01:00Z",
        )

        member_jobs = service.list_jobs_for_user("user_1")
        admin_jobs = service.list_jobs_for_user("admin_1")

        self.assertEqual([job["id"] for job in member_jobs], [first])
        self.assertEqual([job["id"] for job in admin_jobs], [second, first])
        self.assertEqual(member_jobs[0]["source_url_redacted"], "https://example.com/one")

    def test_owner_and_admin_can_read_job_but_other_member_cannot(self):
        service, conn = self._setup_service()
        self._create_user(conn, "owner", "owner@example.com")
        self._create_user(conn, "other", "other@example.com")
        self._create_user(conn, "admin", "admin@example.com", role="admin")
        job_id = self._create_job(
            conn,
            "owner",
            "https://example.com/video",
            "2026-01-01T00:00:00Z",
        )

        self.assertEqual(service.get_job_for_user(job_id, "owner")["id"], job_id)
        self.assertEqual(service.get_job_for_user(job_id, "admin")["id"], job_id)

        with self.assertRaises(ForbiddenJobAccess):
            service.get_job_for_user(job_id, "other")

        with self.assertRaises(JobNotFound):
            service.get_job_for_user("missing", "admin")

    def test_download_path_supports_three_srt_artifacts_for_owner(self):
        service, conn = self._setup_service()
        self._create_user(conn, "owner", "owner@example.com")
        job_id = self._create_job(
            conn,
            "owner",
            "https://example.com/video",
            "2026-01-01T00:00:00Z",
        )
        self._mark_outputs(conn, job_id)

        self.assertEqual(
            service.get_download_path(job_id, "owner", "source.srt"),
            "/tmp/jobs/job/source.srt",
        )
        self.assertEqual(
            service.get_download_path(job_id, "owner", "translated.srt"),
            "/tmp/jobs/job/translated.srt",
        )
        self.assertEqual(
            service.get_download_path(job_id, "owner", "finalized.srt"),
            "/tmp/results/job/finalized.srt",
        )

        with self.assertRaises(InvalidJobArtifact):
            service.get_download_path(job_id, "owner", "video.mp4")

    def test_admin_downloading_other_users_job_writes_audit_log(self):
        service, conn = self._setup_service()
        self._create_user(conn, "owner", "owner@example.com")
        self._create_user(conn, "admin", "admin@example.com", role="admin")
        job_id = self._create_job(
            conn,
            "owner",
            "https://example.com/video",
            "2026-01-01T00:00:00Z",
        )
        self._mark_outputs(conn, job_id)

        path = service.get_download_path(
            job_id,
            "admin",
            "finalized.srt",
            now="2026-01-01T00:02:00Z",
        )

        audit = conn.execute("SELECT * FROM admin_audit_logs").fetchone()
        self.assertEqual(path, "/tmp/results/job/finalized.srt")
        self.assertEqual(audit["actor_user_id"], "admin")
        self.assertEqual(audit["action"], "download_job_artifact")
        self.assertEqual(audit["target_type"], "job")
        self.assertEqual(audit["target_id"], job_id)
        self.assertIn("finalized.srt", audit["metadata_json"])

    def test_member_cannot_download_other_users_job(self):
        service, conn = self._setup_service()
        self._create_user(conn, "owner", "owner@example.com")
        self._create_user(conn, "other", "other@example.com")
        job_id = self._create_job(
            conn,
            "owner",
            "https://example.com/video",
            "2026-01-01T00:00:00Z",
        )
        self._mark_outputs(conn, job_id)

        with self.assertRaises(ForbiddenJobAccess):
            service.get_download_path(job_id, "other", "finalized.srt")


if __name__ == "__main__":
    unittest.main()
