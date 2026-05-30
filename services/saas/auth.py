from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from uuid import uuid4


class InvalidCredentials(ValueError):
    pass


class AccountDisabled(ValueError):
    pass


@dataclass(frozen=True)
class LoginResult:
    user: dict
    session: dict


def hash_password(password: str) -> str:
    salt = hashlib.sha256(uuid4().hex.encode()).digest()[:16]
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex() + ":" + key.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_hex, key_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
        return new_key == expected_key
    except (ValueError, AttributeError):
        return False


class AuthService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def login_with_password(
        self,
        *,
        email: str,
        password: str,
        now: str,
        session_expires_at: str,
    ) -> LoginResult:
        normalized_email = _normalize_email(email)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT * FROM users WHERE email = ?",
                (normalized_email,),
            ).fetchone()
            if row is None:
                raise InvalidCredentials("invalid email or password")
            user = dict(row)
            if user.get("status") == "disabled":
                raise AccountDisabled("account is disabled")
            stored_hash = user.get("password_hash")
            if not stored_hash or not verify_password(password, stored_hash):
                raise InvalidCredentials("invalid email or password")

            session = self._create_session(
                user_id=user["id"],
                created_at=now,
                expires_at=session_expires_at,
            )
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return LoginResult(user=user, session=session)

    def get_current_user(self, session_id: str, *, now: str) -> dict | None:
        row = self.conn.execute(
            """
            SELECT users.*
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.id = ?
              AND sessions.expires_at > ?
              AND users.status = 'active'
            """,
            (session_id, now),
        ).fetchone()
        return dict(row) if row else None

    def logout(self, session_id: str) -> None:
        self.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        self.conn.commit()

    def disable_user(self, user_id: str, *, updated_at: str) -> None:
        self.conn.execute(
            "UPDATE users SET status = 'disabled', updated_at = ? WHERE id = ?",
            (updated_at, user_id),
        )
        self.conn.commit()

    def _create_session(
        self,
        *,
        user_id: str,
        created_at: str,
        expires_at: str,
    ) -> dict:
        session_id = f"sess_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO sessions (id, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, user_id, expires_at, created_at),
        )
        return dict(
            self.conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        )


def _normalize_email(email: str | None) -> str | None:
    return email.strip().lower() if email else None
