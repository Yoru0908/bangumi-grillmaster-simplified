import tempfile
import unittest
from pathlib import Path

from services.saas.auth import (
    AuthService,
    InviteAlreadyUsed,
    InviteExpired,
    InvalidInviteCode,
)
from services.saas.db import connect_database, initialize_database


class SaasAuthFoundationTests(unittest.TestCase):
    def _auth(self) -> AuthService:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect_database(Path(tmp.name) / "app.db")
        self.addCleanup(conn.close)
        initialize_database(conn)
        return AuthService(conn)

    def test_login_with_invite_creates_user_session_and_marks_invite_used(self):
        auth = self._auth()
        auth.create_invite(
            code="invite-123",
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
        )

        result = auth.login_with_invite(
            email="member@example.com",
            code="invite-123",
            now="2026-01-01T01:00:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )

        self.assertEqual(result.user["email"], "member@example.com")
        self.assertEqual(result.user["role"], "member")
        self.assertEqual(result.user["status"], "active")
        self.assertEqual(result.session["user_id"], result.user["id"])
        self.assertEqual(result.session["expires_at"], "2026-02-01T00:00:00Z")

        invite = auth.get_invite("invite-123")
        self.assertEqual(invite["used_by_user_id"], result.user["id"])
        self.assertEqual(invite["used_at"], "2026-01-01T01:00:00Z")

    def test_login_rejects_wrong_email_expired_and_reused_invites(self):
        auth = self._auth()
        auth.create_invite(
            code="invite-123",
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-02T00:00:00Z",
        )

        with self.assertRaises(InvalidInviteCode):
            auth.login_with_invite(
                email="other@example.com",
                code="invite-123",
                now="2026-01-01T01:00:00Z",
                session_expires_at="2026-02-01T00:00:00Z",
            )

        with self.assertRaises(InviteExpired):
            auth.login_with_invite(
                email="member@example.com",
                code="invite-123",
                now="2026-01-03T00:00:00Z",
                session_expires_at="2026-02-01T00:00:00Z",
            )

        auth.login_with_invite(
            email="member@example.com",
            code="invite-123",
            now="2026-01-01T01:00:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )

        with self.assertRaises(InviteAlreadyUsed):
            auth.login_with_invite(
                email="member@example.com",
                code="invite-123",
                now="2026-01-01T02:00:00Z",
                session_expires_at="2026-02-01T00:00:00Z",
            )

    def test_get_current_user_rejects_missing_expired_and_disabled_sessions(self):
        auth = self._auth()
        auth.create_invite(
            code="invite-123",
            email="member@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        result = auth.login_with_invite(
            email="member@example.com",
            code="invite-123",
            now="2026-01-01T01:00:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )

        self.assertEqual(
            auth.get_current_user(
                result.session["id"], now="2026-01-15T00:00:00Z"
            )["id"],
            result.user["id"],
        )
        self.assertIsNone(auth.get_current_user("missing", now="2026-01-15T00:00:00Z"))
        self.assertIsNone(
            auth.get_current_user(
                result.session["id"], now="2026-03-01T00:00:00Z"
            )
        )

        auth.disable_user(result.user["id"], updated_at="2026-01-16T00:00:00Z")
        self.assertIsNone(
            auth.get_current_user(
                result.session["id"], now="2026-01-16T00:00:01Z"
            )
        )

    def test_logout_deletes_only_the_target_session(self):
        auth = self._auth()
        auth.create_invite(
            code="invite-a",
            email="a@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        auth.create_invite(
            code="invite-b",
            email="b@example.com",
            role="member",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        first = auth.login_with_invite(
            email="a@example.com",
            code="invite-a",
            now="2026-01-01T01:00:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )
        second = auth.login_with_invite(
            email="b@example.com",
            code="invite-b",
            now="2026-01-01T01:00:00Z",
            session_expires_at="2026-02-01T00:00:00Z",
        )

        auth.logout(first.session["id"])

        self.assertIsNone(
            auth.get_current_user(
                first.session["id"], now="2026-01-15T00:00:00Z"
            )
        )
        self.assertEqual(
            auth.get_current_user(
                second.session["id"], now="2026-01-15T00:00:00Z"
            )["email"],
            "b@example.com",
        )


if __name__ == "__main__":
    unittest.main()
