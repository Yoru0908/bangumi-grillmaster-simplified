import json
import re
import tempfile
import unittest
from pathlib import Path

from services.saas.auth import AuthService
from services.saas.credits import CreditLedger
from services.saas.db import connect_database, initialize_database
from services.saas.pipeline import PipelineMetadata


class SaasHttpServiceTests(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect_database(Path(tmp.name) / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        AuthService(conn).create_invite(
            code="member-code",
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        AuthService(conn).create_invite(
            code="admin-code",
            email="admin@example.com",
            role="admin",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        return conn

    def _login(
        self,
        app,
        *,
        email: str = "member@example.com",
        invite_code: str = "member-code",
    ) -> str:
        response = app.handle(
            "POST",
            "/api/auth/login",
            headers={},
            body=json.dumps(
                {"email": email, "invite_code": invite_code}
            ).encode("utf-8"),
        )
        self.assertEqual(response.status_code, 200)
        return response.headers["Set-Cookie"].split(";", 1)[0]

    def test_login_sets_http_only_session_cookie_and_me_reads_it(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        session_cookie = self._login(app)
        me = app.handle(
            "GET",
            "/api/auth/me",
            headers={"Cookie": session_cookie},
            body=b"",
        )

        self.assertEqual(me.status_code, 200)
        self.assertIn("HttpOnly", app.last_login_cookie)
        self.assertEqual(me.json_body["user"]["email"], "member@example.com")

    def test_healthz_is_public_and_checks_database(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "GET",
            "/healthz",
            headers={},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json_body, {"ok": True, "database": "ok"})

    def test_root_serves_static_frontend_shell(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "GET",
            "/",
            headers={},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("html", response.headers.get("Content-Type", "").lower())
        html = response.body.decode("utf-8")
        self.assertIn("Kotoba Forge", html)
        self.assertIn("/static/app.js", html)
        self.assertIn('id="language-select"', html)
        for language in ("zh-Hans", "zh-Hant", "en", "ja"):
            self.assertIn(f'value="{language}"', html)

    def test_static_app_js_serves_frontend_bootstrap(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "GET",
            "/static/app.js",
            headers={},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "javascript",
            response.headers.get("Content-Type", "").lower(),
        )
        script = response.body.decode("utf-8")
        self.assertIn("Kotoba Forge", script)
        self.assertIn("const translations", script)
        for language in ("zh-Hans", "zh-Hant", "en", "ja"):
            self.assertIn(language, script)

    def test_static_frontend_routes_do_not_shadow_healthz(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "GET",
            "/healthz",
            headers={},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json_body, {"ok": True, "database": "ok"})

    def test_static_frontend_contains_admin_console_hooks(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        root = app.handle("GET", "/", headers={}, body=b"")
        script = app.handle("GET", "/static/app.js", headers={}, body=b"")

        self.assertEqual(root.status_code, 200)
        self.assertIn("Admin console", root.body.decode("utf-8"))
        self.assertIn("Users &amp; balances", root.body.decode("utf-8"))
        self.assertIn('id="admin-panel"', root.body.decode("utf-8"))
        self.assertEqual(script.status_code, 200)
        script_body = script.body.decode("utf-8")
        self.assertIn("/api/admin/jobs", script_body)
        self.assertIn("/api/admin/users", script_body)
        self.assertIn("/api/admin/audit-logs", script_body)
        self.assertIn("/credits/adjust", script_body)

    def test_static_frontend_separates_playground_paid_and_billing(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        root = app.handle("GET", "/", headers={}, body=b"")
        script = app.handle("GET", "/static/app.js", headers={}, body=b"")

        self.assertEqual(root.status_code, 200)
        html = root.body.decode("utf-8")
        self.assertIn('id="playground-panel"', html)
        self.assertIn('id="paid-workspace-panel"', html)
        self.assertIn('id="billing-panel"', html)
        self.assertIn("Playground", html)
        self.assertIn("Paid workspace", html)
        self.assertIn("Top up credits", html)
        script_body = script.body.decode("utf-8")
        self.assertIn("/api/playground/jobs", script_body)
        self.assertIn("/api/jobs", script_body)
        self.assertIn("topUpTitle", script_body)

    def test_static_css_keeps_left_rail_cards_out_of_sticky_stack(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "GET",
            "/static/styles.css",
            headers={},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        css = response.body.decode("utf-8")
        sticky_rules = [
            selector
            for selector, body in re.findall(r"([^{}]+)\{([^{}]+)\}", css)
            if "position: sticky" in body
        ]
        self.assertFalse(
            any(
                ".account-panel" in selector or ".billing-panel" in selector
                for selector in sticky_rules
            ),
            "Left rail cards must not be sticky; stacked cards overlap.",
        )

    def test_static_frontend_uses_independent_workspace_stacks(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        root = app.handle("GET", "/", headers={}, body=b"")
        styles = app.handle("GET", "/static/styles.css", headers={}, body=b"")

        self.assertEqual(root.status_code, 200)
        html = root.body.decode("utf-8")
        self.assertIn('class="workspace-rail"', html)
        self.assertIn('class="workspace-main"', html)
        rail = html.split('class="workspace-rail"', 1)[1].split(
            'class="workspace-main"', 1
        )[0]
        main = html.split('class="workspace-main"', 1)[1]
        for panel_id in (
            'class="panel account-panel"',
            'id="billing-panel"',
            'class="panel jobs-panel"',
        ):
            self.assertIn(panel_id, rail)
        for panel_id in (
            'id="playground-panel"',
            'id="paid-workspace-panel"',
            'class="panel detail-panel"',
            'id="admin-panel"',
        ):
            self.assertIn(panel_id, main)

        self.assertEqual(styles.status_code, 200)
        css = styles.body.decode("utf-8")
        self.assertRegex(
            css,
            r"\.workspace-rail,\s*\.workspace-main\s*\{[^}]*display:\s*grid;",
        )

    def test_static_frontend_surfaces_failed_job_error_fields(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        script = app.handle("GET", "/static/app.js", headers={}, body=b"")

        self.assertEqual(script.status_code, 200)
        body = script.body.decode("utf-8")
        self.assertIn("failureReasonTitle", body)
        self.assertIn("quotaFailureHint", body)
        self.assertIn("job.error_code", body)
        self.assertIn("job.error_message", body)
        self.assertIn("RESOURCE_EXHAUSTED", body)
        self.assertIn("failure-card", body)

    def test_static_frontend_disables_paid_lane_on_provider_outage(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        root = app.handle("GET", "/", headers={}, body=b"")
        script = app.handle("GET", "/static/app.js", headers={}, body=b"")

        self.assertEqual(root.status_code, 200)
        self.assertIn('id="paid-status-message"', root.body.decode("utf-8"))
        self.assertEqual(script.status_code, 200)
        body = script.body.decode("utf-8")
        self.assertIn("renderProviderStatus", body)
        self.assertIn("isGeminiUnavailable", body)
        self.assertIn("paidButton.disabled = unavailable", body)
        self.assertIn("billing.provider_status", body)

    def test_logout_clears_session_and_cookie(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")
        session_cookie = self._login(app)

        logout = app.handle(
            "POST",
            "/api/auth/logout",
            headers={"Cookie": session_cookie},
            body=b"",
        )
        me = app.handle(
            "GET",
            "/api/auth/me",
            headers={"Cookie": session_cookie},
            body=b"",
        )

        self.assertEqual(logout.status_code, 200)
        self.assertIn("Max-Age=0", logout.headers["Set-Cookie"])
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.json_body["error"]["code"], "AUTH_REQUIRED")

    def test_submit_job_and_list_jobs_over_http(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")
        session_cookie = self._login(app)
        user = conn.execute("SELECT * FROM users WHERE email = ?", ("member@example.com",)).fetchone()
        CreditLedger(conn).grant(
            user_id=user["id"],
            minutes=30,
            reason="test grant",
            idempotency_key="grant-member",
            created_at="2026-01-01T00:02:00Z",
        )

        created = app.handle(
            "POST",
            "/api/jobs",
            headers={"Cookie": session_cookie},
            body=json.dumps({"source_url": "https://example.com/video"}).encode("utf-8"),
        )
        listed = app.handle(
            "GET",
            "/api/jobs",
            headers={"Cookie": session_cookie},
            body=b"",
        )

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json_body["status"], "queued")
        self.assertEqual(
            [job["id"] for job in listed.json_body["jobs"]],
            [created.json_body["job_id"]],
        )

    def test_submit_playground_job_over_http_uses_metadata_gate(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(
            conn,
            now=lambda: "2026-01-01T00:01:00Z",
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        session_cookie = self._login(app)

        response = app.handle(
            "POST",
            "/api/playground/jobs",
            headers={"Cookie": session_cookie},
            body=json.dumps({"source_url": "https://example.com/short"}).encode("utf-8"),
        )

        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (response.json_body["job_id"],)).fetchone()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(job["job_type"], "trial")
        self.assertEqual(job["video_duration_seconds"], 60)

    def test_job_events_route_returns_owner_events(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(
            conn,
            now=lambda: "2026-01-01T00:01:00Z",
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        session_cookie = self._login(app)
        created = app.handle(
            "POST",
            "/api/playground/jobs",
            headers={"Cookie": session_cookie},
            body=json.dumps({"source_url": "https://example.com/short"}).encode("utf-8"),
        )
        conn.execute(
            """
            INSERT INTO job_events (
              id, job_id, level, stage, code, message, created_at
            )
            VALUES ('event_1', ?, 'info', 'created', 'created', 'created', '2026-01-01T00:02:00Z')
            """,
            (created.json_body["job_id"],),
        )
        conn.commit()

        response = app.handle(
            "GET",
            f"/api/jobs/{created.json_body['job_id']}/events",
            headers={"Cookie": session_cookie},
            body=b"",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [event["code"] for event in response.json_body["events"]],
            ["created"],
        )

    def test_download_route_returns_srt_for_owner_and_forbids_other_member(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(
            conn,
            now=lambda: "2026-01-01T00:01:00Z",
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        member_cookie = self._login(app)
        AuthService(conn).create_invite(
            code="other-code",
            email="other@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        other_cookie = self._login(
            app,
            email="other@example.com",
            invite_code="other-code",
        )
        created = app.handle(
            "POST",
            "/api/playground/jobs",
            headers={"Cookie": member_cookie},
            body=json.dumps({"source_url": "https://example.com/short"}).encode("utf-8"),
        )
        result_path = Path(tempfile.gettempdir()) / f"{created.json_body['job_id']}.srt"
        self.addCleanup(lambda: result_path.unlink(missing_ok=True))
        result_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n字幕\n", encoding="utf-8")
        conn.execute(
            """
            UPDATE jobs
            SET status = 'succeeded',
                stage = 'cleanup_completed',
                result_srt_path = ?
            WHERE id = ?
            """,
            (str(result_path), created.json_body["job_id"]),
        )
        conn.commit()

        owner_download = app.handle(
            "GET",
            f"/api/jobs/{created.json_body['job_id']}/download/finalized.srt",
            headers={"Cookie": member_cookie},
            body=b"",
        )
        other_download = app.handle(
            "GET",
            f"/api/jobs/{created.json_body['job_id']}/download/finalized.srt",
            headers={"Cookie": other_cookie},
            body=b"",
        )

        self.assertEqual(owner_download.status_code, 200)
        self.assertEqual(owner_download.body, result_path.read_bytes())
        self.assertIn("attachment", owner_download.headers["Content-Disposition"])
        self.assertEqual(other_download.status_code, 403)
        self.assertEqual(other_download.json_body["error"]["code"], "FORBIDDEN")

    def test_api_errors_are_json_responses(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")

        response = app.handle(
            "POST",
            "/api/jobs",
            headers={},
            body=json.dumps({"source_url": "https://example.com/video"}).encode("utf-8"),
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json_body["error"]["code"], "AUTH_REQUIRED")

    def test_missing_required_fields_are_json_bad_request_responses(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")
        session_cookie = self._login(app)

        missing_source_url = app.handle(
            "POST",
            "/api/jobs",
            headers={"Cookie": session_cookie},
            body=json.dumps({}).encode("utf-8"),
        )
        missing_invite_code = app.handle(
            "POST",
            "/api/auth/login",
            headers={},
            body=json.dumps({"email": "other@example.com"}).encode("utf-8"),
        )

        self.assertEqual(missing_source_url.status_code, 400)
        self.assertEqual(missing_source_url.json_body["error"]["code"], "BAD_REQUEST")
        self.assertEqual(missing_invite_code.status_code, 400)
        self.assertEqual(missing_invite_code.json_body["error"]["code"], "BAD_REQUEST")

    def test_admin_retry_cancel_and_audit_routes(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(
            conn,
            now=lambda: "2026-01-01T00:01:00Z",
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        member_cookie = self._login(app)
        admin_cookie = self._login(
            app,
            email="admin@example.com",
            invite_code="admin-code",
        )
        created = app.handle(
            "POST",
            "/api/playground/jobs",
            headers={"Cookie": member_cookie},
            body=json.dumps({"source_url": "https://example.com/short"}).encode("utf-8"),
        )
        job_id = created.json_body["job_id"]
        conn.execute(
            "UPDATE jobs SET status = 'failed', error_code = 'GEMINI_FAILED' WHERE id = ?",
            (job_id,),
        )
        conn.commit()

        retry = app.handle(
            "POST",
            f"/api/admin/jobs/{job_id}/retry",
            headers={"Cookie": admin_cookie},
            body=b"",
        )
        cancel = app.handle(
            "DELETE",
            f"/api/admin/jobs/{job_id}",
            headers={"Cookie": admin_cookie},
            body=json.dumps({"reason": "test"}).encode("utf-8"),
        )
        audits = app.handle(
            "GET",
            "/api/admin/audit-logs",
            headers={"Cookie": admin_cookie},
            body=b"",
        )

        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json_body["status"], "queued")
        self.assertEqual(cancel.status_code, 200)
        self.assertEqual(cancel.json_body["status"], "cancelled")
        self.assertEqual(
            [row["action"] for row in audits.json_body["audit_logs"]],
            ["admin_cancel_job", "admin_retry_job"],
        )

    def test_admin_credit_adjust_route_requires_admin_and_updates_billing(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")
        member_cookie = self._login(app)
        member = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            ("member@example.com",),
        ).fetchone()
        admin_cookie = self._login(
            app,
            email="admin@example.com",
            invite_code="admin-code",
        )

        forbidden = app.handle(
            "POST",
            f"/api/admin/users/{member['id']}/credits/adjust",
            headers={"Cookie": member_cookie},
            body=json.dumps({"minutes": 5, "reason": "member attempt"}).encode("utf-8"),
        )
        adjusted = app.handle(
            "POST",
            f"/api/admin/users/{member['id']}/credits/adjust",
            headers={"Cookie": admin_cookie},
            body=json.dumps({"minutes": 12, "reason": "admin grant"}).encode("utf-8"),
        )
        billing = app.handle(
            "GET",
            "/api/billing",
            headers={"Cookie": member_cookie},
            body=b"",
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json_body["error"]["code"], "FORBIDDEN")
        self.assertEqual(adjusted.status_code, 200)
        self.assertEqual(adjusted.json_body["balance_minutes"], 12)
        self.assertEqual(billing.json_body["balance_minutes"], 12)

    def test_admin_users_route_lists_users_with_credit_balances(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(conn, now=lambda: "2026-01-01T00:01:00Z")
        member_cookie = self._login(app)
        member = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            ("member@example.com",),
        ).fetchone()
        CreditLedger(conn).grant(
            user_id=member["id"],
            minutes=7,
            reason="test grant",
            idempotency_key="admin-users-grant",
            created_at="2026-01-01T00:02:00Z",
        )
        admin_cookie = self._login(
            app,
            email="admin@example.com",
            invite_code="admin-code",
        )

        forbidden = app.handle(
            "GET",
            "/api/admin/users",
            headers={"Cookie": member_cookie},
            body=b"",
        )
        allowed = app.handle(
            "GET",
            "/api/admin/users",
            headers={"Cookie": admin_cookie},
            body=b"",
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json_body["error"]["code"], "FORBIDDEN")
        self.assertEqual(allowed.status_code, 200)
        users_by_email = {
            user["email"]: user for user in allowed.json_body["users"]
        }
        self.assertEqual(users_by_email["member@example.com"]["id"], member["id"])
        self.assertEqual(users_by_email["member@example.com"]["balance_minutes"], 7)
        self.assertEqual(users_by_email["admin@example.com"]["role"], "admin")

    def test_admin_jobs_route_requires_admin(self):
        from services.saas.http_service import SaasHttpApp

        conn = self._setup()
        app = SaasHttpApp(
            conn,
            now=lambda: "2026-01-01T00:01:00Z",
            metadata_fetcher=lambda url: PipelineMetadata(
                video_title="short",
                video_duration_seconds=60,
            ),
        )
        member_cookie = self._login(app)
        admin_cookie = self._login(
            app,
            email="admin@example.com",
            invite_code="admin-code",
        )
        created = app.handle(
            "POST",
            "/api/playground/jobs",
            headers={"Cookie": member_cookie},
            body=json.dumps({"source_url": "https://example.com/short"}).encode("utf-8"),
        )

        forbidden = app.handle(
            "GET",
            "/api/admin/jobs",
            headers={"Cookie": member_cookie},
            body=b"",
        )
        allowed = app.handle(
            "GET",
            "/api/admin/jobs",
            headers={"Cookie": admin_cookie},
            body=b"",
        )

        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.json_body["error"]["code"], "FORBIDDEN")
        self.assertEqual(
            [job["id"] for job in allowed.json_body["jobs"]],
            [created.json_body["job_id"]],
        )


if __name__ == "__main__":
    unittest.main()
