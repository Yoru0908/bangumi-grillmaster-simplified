import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from settings import settings
from services.saas.api_service import ApiError, SaasApiService
from services.saas.auth import AuthService
from services.saas.credits import CreditLedger
from services.saas.db import connect_database, initialize_database
from services.saas.pipeline import PipelineMetadata


class SaasApiServiceTests(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect_database(Path(tmp.name) / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        auth = AuthService(conn)
        auth.create_invite(
            code="member-code",
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        auth.create_invite(
            code="other-code",
            email="other@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        auth.create_invite(
            code="admin-code",
            email="admin@example.com",
            role="admin",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        member = auth.login_with_invite(
            email="member@example.com",
            code="member-code",
            now="2026-01-01T00:01:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )
        other = auth.login_with_invite(
            email="other@example.com",
            code="other-code",
            now="2026-01-01T00:01:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )
        admin = auth.login_with_invite(
            email="admin@example.com",
            code="admin-code",
            now="2026-01-01T00:01:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )
        return conn, member, other, admin

    def _write_event(
        self,
        conn,
        *,
        job_id: str,
        code: str,
        created_at: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO job_events (
              id, job_id, level, stage, code, message, metadata_json, created_at
            )
            VALUES (?, ?, 'info', 'created', ?, ?, ?, ?)
            """,
            (
                f"event_{uuid4().hex}",
                job_id,
                code,
                code,
                json.dumps({"code": code}),
                created_at,
            ),
        )
        conn.commit()

    def test_submit_job_requires_auth_and_minimum_credit_balance(self):
        conn, member, _, _ = self._setup()
        service = SaasApiService(conn, min_submit_credit_minutes=10)

        with self.assertRaises(ApiError) as missing_auth:
            service.submit_job(
                session_id=None,
                source_url="https://example.com/video",
                now="2026-01-01T00:02:00Z",
            )
        self.assertEqual(missing_auth.exception.status_code, 401)
        self.assertEqual(missing_auth.exception.code, "AUTH_REQUIRED")

        with self.assertRaises(ApiError) as low_balance:
            service.submit_job(
                session_id=member.session["id"],
                source_url="https://example.com/video",
                now="2026-01-01T00:02:00Z",
            )
        self.assertEqual(low_balance.exception.status_code, 400)
        self.assertEqual(low_balance.exception.code, "INSUFFICIENT_CREDITS")

    def test_submit_job_creates_queued_job_when_balance_is_enough(self):
        conn, member, _, _ = self._setup()
        CreditLedger(conn).grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member",
            created_at="2026-01-01T00:02:00Z",
        )
        service = SaasApiService(conn, min_submit_credit_minutes=10)

        response = service.submit_job(
            session_id=member.session["id"],
            source_url="https://example.com/video?token=secret",
            now="2026-01-01T00:03:00Z",
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (response["job_id"],)).fetchone()
        self.assertEqual(response["status"], "queued")
        self.assertEqual(response["stage"], "created")
        self.assertEqual(job["source_url"], "https://example.com/video?token=secret")
        self.assertEqual(job["source_url_redacted"], "https://example.com/video")

    def test_submit_job_rejects_invalid_url_before_enqueue(self):
        conn, member, _, _ = self._setup()
        CreditLedger(conn).grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member",
            created_at="2026-01-01T00:02:00Z",
        )
        service = SaasApiService(conn, min_submit_credit_minutes=10)

        with self.assertRaises(ApiError) as invalid_url:
            service.submit_job(
                session_id=member.session["id"],
                source_url="not-a-url",
                now="2026-01-01T00:03:00Z",
            )

        self.assertEqual(invalid_url.exception.status_code, 400)
        self.assertEqual(invalid_url.exception.code, "INVALID_URL")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_submit_playground_job_allows_short_url_without_credit_balance(self):
        conn, member, _, _ = self._setup()
        calls = []
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: calls.append(url)
            or PipelineMetadata(video_title="short", video_duration_seconds=60),
        )

        response = service.submit_playground_job(
            session_id=member.session["id"],
            source_url="https://example.com/short",
            now="2026-01-01T00:03:00Z",
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (response["job_id"],)).fetchone()
        self.assertEqual(calls, ["https://example.com/short"])
        self.assertEqual(response["status"], "queued")
        self.assertEqual(job["video_title"], "short")
        self.assertEqual(job["video_duration_seconds"], 60)
        self.assertEqual(job["job_type"], "trial")

    def test_submit_playground_job_rejects_url_longer_than_one_minute(self):
        conn, member, _, _ = self._setup()
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="long",
                video_duration_seconds=61,
            ),
        )

        with self.assertRaises(ApiError) as too_long:
            service.submit_playground_job(
                session_id=member.session["id"],
                source_url="https://example.com/long",
                now="2026-01-01T00:03:00Z",
            )

        self.assertEqual(too_long.exception.status_code, 400)
        self.assertEqual(too_long.exception.code, "TRIAL_VIDEO_TOO_LONG")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_submit_playground_job_rejects_private_url_before_metadata_fetch(self):
        conn, member, _, _ = self._setup()
        calls = []
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: calls.append(url)
            or PipelineMetadata(video_title="private", video_duration_seconds=60),
        )

        with self.assertRaises(ApiError) as forbidden_url:
            service.submit_playground_job(
                session_id=member.session["id"],
                source_url="http://127.0.0.1:9000/video",
                now="2026-01-01T00:03:00Z",
            )

        self.assertEqual(forbidden_url.exception.status_code, 400)
        self.assertEqual(forbidden_url.exception.code, "FORBIDDEN_URL")
        self.assertEqual(calls, [])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)

    def test_list_and_detail_are_scoped_to_current_user(self):
        conn, member, other, _ = self._setup()
        ledger = CreditLedger(conn)
        ledger.grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member",
            created_at="2026-01-01T00:02:00Z",
        )
        ledger.grant(
            user_id=other.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-other",
            created_at="2026-01-01T00:02:00Z",
        )
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        member_job = service.submit_job(
            session_id=member.session["id"],
            source_url="https://example.com/member",
            now="2026-01-01T00:03:00Z",
        )
        other_job = service.submit_job(
            session_id=other.session["id"],
            source_url="https://example.com/other",
            now="2026-01-01T00:04:00Z",
        )

        self.assertEqual(
            [job["id"] for job in service.list_jobs(member.session["id"], now="2026-01-01T00:05:00Z")],
            [member_job["job_id"]],
        )
        self.assertEqual(
            service.get_job(member.session["id"], member_job["job_id"], now="2026-01-01T00:05:00Z")["id"],
            member_job["job_id"],
        )
        with self.assertRaises(ApiError) as forbidden:
            service.get_job(member.session["id"], other_job["job_id"], now="2026-01-01T00:05:00Z")
        self.assertEqual(forbidden.exception.status_code, 403)
        self.assertEqual(forbidden.exception.code, "FORBIDDEN")

    def test_download_path_uses_job_access_permissions(self):
        conn, member, other, _ = self._setup()
        CreditLedger(conn).grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member",
            created_at="2026-01-01T00:02:00Z",
        )
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        response = service.submit_job(
            session_id=member.session["id"],
            source_url="https://example.com/member",
            now="2026-01-01T00:03:00Z",
        )
        conn.execute(
            """
            UPDATE jobs
            SET status = 'succeeded',
                stage = 'cleanup_completed',
                result_srt_path = '/tmp/finalized.srt'
            WHERE id = ?
            """,
            (response["job_id"],),
        )
        conn.commit()

        self.assertEqual(
            service.get_download_path(
                member.session["id"],
                response["job_id"],
                "finalized.srt",
                now="2026-01-01T00:04:00Z",
            ),
            "/tmp/finalized.srt",
        )
        with self.assertRaises(ApiError) as forbidden:
            service.get_download_path(
                other.session["id"],
                response["job_id"],
                "finalized.srt",
                now="2026-01-01T00:04:00Z",
            )
        self.assertEqual(forbidden.exception.status_code, 403)

    def test_get_job_events_are_scoped_to_owner_and_admin(self):
        conn, member, other, admin = self._setup()
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        response = service.submit_playground_job(
            session_id=member.session["id"],
            source_url="https://example.com/short",
            now="2026-01-01T00:03:00Z",
        )
        self._write_event(
            conn,
            job_id=response["job_id"],
            code="first",
            created_at="2026-01-01T00:04:00Z",
        )
        self._write_event(
            conn,
            job_id=response["job_id"],
            code="second",
            created_at="2026-01-01T00:05:00Z",
        )

        owner_events = service.get_job_events(
            member.session["id"],
            response["job_id"],
            now="2026-01-01T00:06:00Z",
        )
        admin_events = service.get_job_events(
            admin.session["id"],
            response["job_id"],
            now="2026-01-01T00:06:00Z",
        )

        self.assertEqual([event["code"] for event in owner_events], ["first", "second"])
        self.assertEqual(owner_events[0]["metadata"], {"code": "first"})
        self.assertEqual([event["code"] for event in admin_events], ["first", "second"])
        with self.assertRaises(ApiError) as forbidden:
            service.get_job_events(
                other.session["id"],
                response["job_id"],
                now="2026-01-01T00:06:00Z",
            )
        self.assertEqual(forbidden.exception.status_code, 403)

    def test_billing_balance_and_admin_adjustment(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(conn)

        with self.assertRaises(ApiError) as forbidden:
            service.admin_adjust_credits(
                admin_session_id=member.session["id"],
                target_user_id=member.user["id"],
                minutes=20,
                reason="test",
                now="2026-01-01T00:02:00Z",
            )
        self.assertEqual(forbidden.exception.status_code, 403)

        service.admin_adjust_credits(
            admin_session_id=admin.session["id"],
            target_user_id=member.user["id"],
            minutes=20,
            reason="test",
            now="2026-01-01T00:02:00Z",
        )

        self.assertEqual(
            service.get_billing_summary(member.session["id"], now="2026-01-01T00:03:00Z")[
                "balance_minutes"
            ],
            20,
        )

    def test_billing_summary_reports_gemini_quota_outage(self):
        conn, member, _, _ = self._setup()
        service = SaasApiService(conn)
        job_id = f"job_{uuid4().hex}"
        conn.execute(
            """
            INSERT INTO jobs (
              id, user_id, job_type, source_url, source_url_redacted,
              status, stage, error_code, error_message, created_at, finished_at
            )
            VALUES (
              ?, ?, 'paid', 'https://example.com/video', 'https://example.com/video',
              'failed', 'metadata_fetched', 'GEMINI_QUOTA_EXHAUSTED',
              'Pre-pass failed: RESOURCE_EXHAUSTED', ?, ?
            )
            """,
            (
                job_id,
                member.user["id"],
                "2026-01-01T00:02:00Z",
                "2026-01-01T00:03:00Z",
            ),
        )
        conn.commit()

        with patch.object(settings, "gemini_backend", "google_genai"):
            summary = service.get_billing_summary(
                member.session["id"], now="2026-01-01T00:04:00Z"
            )

        self.assertFalse(summary["provider_status"]["gemini"]["available"])
        self.assertEqual(
            summary["provider_status"]["gemini"]["code"],
            "GEMINI_QUOTA_EXHAUSTED",
        )
        self.assertIn(
            "RESOURCE_EXHAUSTED", summary["provider_status"]["gemini"]["message"]
        )

    def test_billing_summary_ignores_google_quota_history_when_agent_platform_is_active(self):
        conn, member, _, _ = self._setup()
        service = SaasApiService(conn)
        conn.execute(
            """
            INSERT INTO jobs (
              id, user_id, job_type, source_url, source_url_redacted,
              status, stage, error_code, error_message, created_at, finished_at
            )
            VALUES (
              ?, ?, 'paid', 'https://example.com/video', 'https://example.com/video',
              'failed', 'metadata_fetched', 'GEMINI_QUOTA_EXHAUSTED',
              'Pre-pass failed: RESOURCE_EXHAUSTED', ?, ?
            )
            """,
            (
                f"job_{uuid4().hex}",
                member.user["id"],
                "2026-01-01T00:02:00Z",
                "2026-01-01T00:03:00Z",
            ),
        )
        conn.commit()

        with patch.object(settings, "gemini_backend", "agent_platform"):
            summary = service.get_billing_summary(
                member.session["id"], now="2026-01-01T00:04:00Z"
            )

        self.assertTrue(summary["provider_status"]["gemini"]["available"])
        self.assertIsNone(summary["provider_status"]["gemini"]["code"])

    def test_admin_retry_failed_job_requires_admin_and_writes_audit(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        job_id = service.submit_playground_job(
            session_id=member.session["id"],
            source_url="https://example.com/short",
            now="2026-01-01T00:02:00Z",
        )["job_id"]
        conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                stage = 'metadata_fetched',
                error_code = 'GEMINI_FAILED',
                error_message = 'temporary upstream failure',
                worker_id = 'worker-old',
                heartbeat_at = '2026-01-01T00:03:00Z',
                started_at = '2026-01-01T00:02:00Z',
                finished_at = '2026-01-01T00:04:00Z',
                retry_count = 1
            WHERE id = ?
            """,
            (job_id,),
        )
        conn.commit()

        with self.assertRaises(ApiError) as forbidden:
            service.admin_retry_job(
                admin_session_id=member.session["id"],
                job_id=job_id,
                now="2026-01-01T00:05:00Z",
            )
        self.assertEqual(forbidden.exception.status_code, 403)

        response = service.admin_retry_job(
            admin_session_id=admin.session["id"],
            job_id=job_id,
            now="2026-01-01T00:05:00Z",
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        audit = conn.execute("SELECT * FROM admin_audit_logs").fetchone()
        self.assertEqual(response["status"], "queued")
        self.assertEqual(job["status"], "queued")
        self.assertEqual(job["stage"], "created")
        self.assertEqual(job["error_code"], None)
        self.assertEqual(job["worker_id"], None)
        self.assertEqual(job["retry_count"], 2)
        self.assertEqual(audit["action"], "admin_retry_job")
        self.assertEqual(audit["target_id"], job_id)

    def test_admin_list_jobs_requires_admin(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        job_id = service.submit_playground_job(
            session_id=member.session["id"],
            source_url="https://example.com/short",
            now="2026-01-01T00:02:00Z",
        )["job_id"]

        with self.assertRaises(ApiError) as forbidden:
            service.admin_list_jobs(
                admin_session_id=member.session["id"],
                now="2026-01-01T00:03:00Z",
            )

        self.assertEqual(forbidden.exception.status_code, 403)
        self.assertEqual(
            [job["id"] for job in service.admin_list_jobs(
                admin_session_id=admin.session["id"],
                now="2026-01-01T00:03:00Z",
            )],
            [job_id],
        )

    def test_admin_cancel_job_and_list_audit_logs(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(
            conn,
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        job_id = service.submit_playground_job(
            session_id=member.session["id"],
            source_url="https://example.com/short",
            now="2026-01-01T00:02:00Z",
        )["job_id"]

        with self.assertRaises(ApiError) as forbidden:
            service.admin_cancel_job(
                admin_session_id=member.session["id"],
                job_id=job_id,
                reason="test cancel",
                now="2026-01-01T00:03:00Z",
            )
        self.assertEqual(forbidden.exception.status_code, 403)

        response = service.admin_cancel_job(
            admin_session_id=admin.session["id"],
            job_id=job_id,
            reason="test cancel",
            now="2026-01-01T00:03:00Z",
        )
        service.admin_adjust_credits(
            admin_session_id=admin.session["id"],
            target_user_id=member.user["id"],
            minutes=5,
            reason="audit order",
            now="2026-01-01T00:04:00Z",
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        audits = service.admin_list_audit_logs(
            admin_session_id=admin.session["id"],
            now="2026-01-01T00:05:00Z",
        )
        self.assertEqual(response["status"], "cancelled")
        self.assertEqual(job["status"], "cancelled")
        self.assertEqual(job["progress_message"], "cancelled by admin")
        self.assertEqual(
            [row["action"] for row in audits],
            ["admin_credit_adjustment", "admin_cancel_job"],
        )
        self.assertEqual(audits[0]["metadata"]["minutes"], 5)
        self.assertEqual(audits[1]["metadata"]["reason"], "test cancel")

    def test_admin_cancel_refunds_reserved_but_unconsumed_credits(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(conn)
        CreditLedger(conn).grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member-cancel",
            created_at="2026-01-01T00:02:00Z",
        )
        job_id = service.submit_job(
            session_id=member.session["id"],
            source_url="https://example.com/video",
            now="2026-01-01T00:03:00Z",
        )["job_id"]
        CreditLedger(conn).reserve(
            user_id=member.user["id"],
            job_id=job_id,
            minutes=10,
            idempotency_key=f"reserve:{job_id}",
            created_at="2026-01-01T00:04:00Z",
        )

        service.admin_cancel_job(
            admin_session_id=admin.session["id"],
            job_id=job_id,
            reason="stop",
            now="2026-01-01T00:05:00Z",
        )

        balance = conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = ?",
            (member.user["id"],),
        ).fetchone()["balance_minutes"]
        ledger_types = [
            row["type"]
            for row in conn.execute(
                "SELECT type FROM credit_ledger ORDER BY created_at, rowid"
            )
        ]
        self.assertEqual(balance, 30)
        self.assertEqual(ledger_types, ["grant", "reserve", "refund"])

    def test_admin_cancel_refunds_only_unconsumed_reserved_credits(self):
        conn, member, _, admin = self._setup()
        service = SaasApiService(conn)
        CreditLedger(conn).grant(
            user_id=member.user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member-consumed-cancel",
            created_at="2026-01-01T00:02:00Z",
        )
        job_id = service.submit_job(
            session_id=member.session["id"],
            source_url="https://example.com/video",
            now="2026-01-01T00:03:00Z",
        )["job_id"]
        ledger = CreditLedger(conn)
        ledger.reserve(
            user_id=member.user["id"],
            job_id=job_id,
            minutes=10,
            idempotency_key=f"reserve:{job_id}",
            created_at="2026-01-01T00:04:00Z",
        )
        ledger.consume(
            user_id=member.user["id"],
            job_id=job_id,
            minutes=4,
            idempotency_key=f"consume:{job_id}",
            created_at="2026-01-01T00:04:30Z",
        )

        service.admin_cancel_job(
            admin_session_id=admin.session["id"],
            job_id=job_id,
            reason="stop",
            now="2026-01-01T00:05:00Z",
        )

        balance = conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = ?",
            (member.user["id"],),
        ).fetchone()["balance_minutes"]
        refund = conn.execute(
            "SELECT minutes FROM credit_ledger WHERE type = 'refund'"
        ).fetchone()
        self.assertEqual(balance, 26)
        self.assertEqual(refund["minutes"], 6)


if __name__ == "__main__":
    unittest.main()
