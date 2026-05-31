from __future__ import annotations

import os
from pathlib import Path
import ipaddress
import json
import sqlite3
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4

from services.saas.auth import AuthService
from services.saas.credits import CreditLedger
from services.saas.job_access import (
    ForbiddenJobAccess,
    InvalidJobArtifact,
    JobAccessService,
    JobNotFound,
)
from services.saas.jobs import JobStore
from services.saas.pipeline import WorkflowSubtitlePipeline
from settings import settings


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    role: str


class SaasApiService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        min_submit_credit_minutes: float = 10,
        trial_max_duration_seconds: int = 60,
        metadata_fetcher=None,
    ):
        self.conn = conn
        self.min_submit_credit_minutes = min_submit_credit_minutes
        self.trial_max_duration_seconds = trial_max_duration_seconds
        self.metadata_fetcher = metadata_fetcher

    def submit_job(
        self,
        *,
        session_id: str | None,
        source_url: str,
        now: str,
    ) -> dict:
        user = self._require_user(session_id, now=now)
        _validate_public_url(source_url)
        if user.role != "admin" and self._balance(user.id) < self.min_submit_credit_minutes:
            raise ApiError(
                400,
                "INSUFFICIENT_CREDITS",
                "Not enough credits to submit a job",
            )
        job_id = JobStore(self.conn).create_job(
            user_id=user.id,
            source_url=source_url,
            now=now,
        )
        return {"job_id": job_id, "status": "queued", "stage": "created"}

    def submit_playground_job(
        self,
        *,
        session_id: str | None,
        source_url: str,
        now: str,
    ) -> dict:
        user = self._require_user(session_id, now=now)
        _validate_public_url(source_url)
        metadata = self._fetch_metadata(source_url)
        if metadata.video_duration_seconds > self.trial_max_duration_seconds:
            raise ApiError(
                400,
                "TRIAL_VIDEO_TOO_LONG",
                "Playground trial only accepts videos up to 60 seconds",
            )
        job_id = JobStore(self.conn).create_job(
            user_id=user.id,
            source_url=source_url,
            now=now,
            job_type="trial",
            video_title=metadata.video_title,
            video_duration_seconds=metadata.video_duration_seconds,
        )
        return {"job_id": job_id, "status": "queued", "stage": "created"}

    def submit_upload_job(
        self,
        *,
        session_id: str | None,
        filename: str,
        file_content: bytes,
        now: str,
    ) -> dict:
        user = self._require_user(session_id, now=now)
        if user.role != "admin" and self._balance(user.id) < self.min_submit_credit_minutes:
            raise ApiError(400, "INSUFFICIENT_CREDITS", "Not enough credits to submit a job")
        from services.saas.jobs import JobStore
        store = JobStore(self.conn)
        job_id = store.create_job(user_id=user.id, source_url=f"upload://{filename}", now=now, job_type="paid")
        upload_dir = Path(os.environ.get("SAAS_JOB_DATA_DIR", "/tmp")) / "uploads" / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        (upload_dir / filename).write_bytes(file_content)
        return {"job_id": job_id, "status": "queued", "stage": "created"}

    def submit_r2_job(
        self,
        *,
        session_id: str | None,
        r2_key: str,
        filename: str,
        now: str,
    ) -> dict:
        user = self._require_user(session_id, now=now)
        if user.role != "admin" and self._balance(user.id) < self.min_submit_credit_minutes:
            raise ApiError(400, "INSUFFICIENT_CREDITS", "Not enough credits to submit a job")
        from services.saas.r2 import download_from_r2
        from services.saas.jobs import JobStore
        job_id = JobStore(self.conn).create_job(user_id=user.id, source_url=f"upload://{filename}", now=now, job_type="paid")
        upload_dir = Path(os.environ.get("SAAS_JOB_DATA_DIR", "/tmp")) / "uploads" / job_id
        upload_dir.mkdir(parents=True, exist_ok=True)
        dest = upload_dir / filename
        download_from_r2(r2_key, str(dest))
        return {"job_id": job_id, "status": "queued", "stage": "created"}

    def submit_playground_job_anonymous(
        self,
        *,
        source_url: str,
        now: str,
    ) -> dict:
        _validate_public_url(source_url)
        metadata = self._fetch_metadata(source_url)
        if metadata.video_duration_seconds > self.trial_max_duration_seconds:
            raise ApiError(400, "TRIAL_TOO_LONG", "Video too long for playground trial")
        job_id = JobStore(self.conn).create_anonymous_trial_job(source_url=source_url, now=now)
        return {"job_id": job_id, "status": "queued", "stage": "created"}

    def list_jobs(self, session_id: str | None, *, now: str) -> list[dict]:
        user = self._require_user(session_id, now=now)
        return JobAccessService(self.conn).list_jobs_for_user(user.id)

    def admin_list_jobs(
        self,
        *,
        admin_session_id: str | None,
        now: str,
    ) -> list[dict]:
        self._require_admin(admin_session_id, now=now)
        rows = self.conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

    def admin_list_users(
        self,
        *,
        admin_session_id: str | None,
        now: str,
    ) -> list[dict]:
        self._require_admin(admin_session_id, now=now)
        rows = self.conn.execute(
            """
            SELECT
              users.id,
              users.email,
              users.role,
              users.status,
              users.created_at,
              users.updated_at,
              COALESCE(credit_balances.balance_minutes, 0) AS balance_minutes
            FROM users
            LEFT JOIN credit_balances ON credit_balances.user_id = users.id
            ORDER BY users.email ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def get_job(self, session_id: str | None, job_id: str, *, now: str) -> dict:
        user = self._require_user(session_id, now=now)
        try:
            return JobAccessService(self.conn).get_job_for_user(job_id, user.id)
        except JobNotFound as exc:
            raise ApiError(404, "JOB_NOT_FOUND", str(exc)) from exc
        except ForbiddenJobAccess as exc:
            raise ApiError(403, "FORBIDDEN", str(exc)) from exc

    def get_job_events(
        self,
        session_id: str | None,
        job_id: str,
        *,
        now: str,
    ) -> list[dict]:
        user = self._require_user(session_id, now=now)
        try:
            JobAccessService(self.conn).get_job_for_user(job_id, user.id)
        except JobNotFound as exc:
            raise ApiError(404, "JOB_NOT_FOUND", str(exc)) from exc
        except ForbiddenJobAccess as exc:
            raise ApiError(403, "FORBIDDEN", str(exc)) from exc
        rows = self.conn.execute(
            """
            SELECT id, level, stage, code, message, metadata_json, created_at
            FROM job_events
            WHERE job_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (job_id,),
        ).fetchall()
        return [_event_row(row) for row in rows]

    def get_download_path(
        self,
        session_id: str | None,
        job_id: str,
        artifact: str,
        *,
        now: str,
    ) -> str:
        user = self._require_user(session_id, now=now)
        try:
            return JobAccessService(self.conn).get_download_path(
                job_id,
                user.id,
                artifact,
                now=now,
            )
        except JobNotFound as exc:
            raise ApiError(404, "JOB_NOT_FOUND", str(exc)) from exc
        except ForbiddenJobAccess as exc:
            raise ApiError(403, "FORBIDDEN", str(exc)) from exc
        except InvalidJobArtifact as exc:
            raise ApiError(404, "ARTIFACT_NOT_FOUND", str(exc)) from exc

    def get_billing_summary(self, session_id: str | None, *, now: str) -> dict:
        user = self._require_user(session_id, now=now)
        rows = self.conn.execute(
            """
            SELECT type, minutes, reason, created_at
            FROM credit_ledger
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (user.id,),
        ).fetchall()
        return {
            "balance_minutes": self._balance(user.id),
            "recent_ledger": [dict(row) for row in rows],
            "provider_status": self._provider_status(),
        }

    def admin_adjust_credits(
        self,
        *,
        admin_session_id: str | None,
        target_user_id: str,
        minutes: float,
        reason: str,
        now: str,
    ) -> dict:
        admin = self._require_user(admin_session_id, now=now)
        if admin.role != "admin":
            raise ApiError(403, "FORBIDDEN", "Admin role required")
        balance = CreditLedger(self.conn).adjustment(
            user_id=target_user_id,
            minutes=minutes,
            reason=reason,
            idempotency_key=f"admin-adjust:{target_user_id}:{uuid4().hex}",
            created_at=now,
            created_by_user_id=admin.id,
        )
        self._write_admin_audit(
            actor_user_id=admin.id,
            target_user_id=target_user_id,
            minutes=minutes,
            reason=reason,
            created_at=now,
        )
        return {"user_id": target_user_id, "balance_minutes": balance}

    def admin_retry_job(
        self,
        *,
        admin_session_id: str | None,
        job_id: str,
        now: str,
    ) -> dict:
        admin = self._require_admin(admin_session_id, now=now)
        job = self._get_job(job_id)
        if job["status"] != "failed":
            raise ApiError(400, "INVALID_JOB_STATE", "Only failed jobs can be retried")
        retry_count = int(job["retry_count"]) + 1
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'queued',
                stage = 'created',
                progress_message = 'queued for retry',
                error_code = NULL,
                error_message = NULL,
                worker_id = NULL,
                heartbeat_at = NULL,
                started_at = NULL,
                finished_at = NULL,
                retry_count = ?,
                retry_after_seconds = NULL,
                source_srt_path = NULL,
                translated_srt_path = NULL,
                result_srt_path = NULL
            WHERE id = ?
            """,
            (retry_count, job_id),
        )
        self._write_audit(
            actor_user_id=admin.id,
            action="admin_retry_job",
            target_type="job",
            target_id=job_id,
            metadata={"retry_count": retry_count},
            created_at=now,
        )
        self.conn.commit()
        return {"job_id": job_id, "status": "queued", "retry_count": retry_count}

    def admin_cancel_job(
        self,
        *,
        admin_session_id: str | None,
        job_id: str,
        reason: str,
        now: str,
    ) -> dict:
        admin = self._require_admin(admin_session_id, now=now)
        job = self._get_job(job_id)
        refundable_minutes = max(
            0.0,
            float(job["reserved_minutes"]) - float(job["consumed_minutes"]),
        )
        if refundable_minutes > 0:
            CreditLedger(self.conn).refund(
                user_id=job["user_id"],
                job_id=job_id,
                minutes=refundable_minutes,
                idempotency_key=f"admin-cancel-refund:{job_id}",
                created_at=now,
                reason="admin cancel refund",
            )
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'cancelled',
                progress_message = 'cancelled by admin',
                worker_id = NULL,
                heartbeat_at = NULL,
                finished_at = ?
            WHERE id = ?
            """,
            (now, job_id),
        )
        self._write_audit(
            actor_user_id=admin.id,
            action="admin_cancel_job",
            target_type="job",
            target_id=job_id,
            metadata={"reason": reason},
            created_at=now,
        )
        self.conn.commit()
        return {"job_id": job_id, "status": "cancelled"}

    def admin_list_audit_logs(
        self,
        *,
        admin_session_id: str | None,
        now: str,
        limit: int = 100,
    ) -> list[dict]:
        self._require_admin(admin_session_id, now=now)
        rows = self.conn.execute(
            """
            SELECT *
            FROM admin_audit_logs
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_audit_row(row) for row in rows]

    def grant_credits_from_stripe(self, user_id: str, minutes: int) -> None:
        """Grant credits from Stripe payment. Idempotent per stripe session."""
        from services.saas.credits import CreditLedger
        from datetime import datetime, timezone
        import uuid as _uuid
        CreditLedger(self.conn).grant(
            user_id=user_id,
            minutes=float(minutes),
            reason=f"stripe top-up: {minutes}min",
            idempotency_key=f"stripe:{user_id}:{_uuid.uuid4().hex[:12]}",
            created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def _require_user(self, session_id: str | None, *, now: str) -> CurrentUser:
        if not session_id:
            raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
        user = AuthService(self.conn).get_current_user(session_id, now=now)
        if user is None:
            raise ApiError(401, "AUTH_REQUIRED", "Authentication required")
        return CurrentUser(id=user["id"], email=user["email"], role=user["role"])

    def _require_admin(self, session_id: str | None, *, now: str) -> CurrentUser:
        user = self._require_user(session_id, now=now)
        if user.role != "admin":
            raise ApiError(403, "FORBIDDEN", "Admin role required")
        return user

    def _get_job(self, job_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise ApiError(404, "JOB_NOT_FOUND", "job not found")
        return row

    def _balance(self, user_id: str) -> float:
        row = self.conn.execute(
            "SELECT balance_minutes FROM credit_balances WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        return float(row["balance_minutes"]) if row else 0.0

    def _fetch_metadata(self, source_url: str):
        if self.metadata_fetcher is not None:
            return self.metadata_fetcher(source_url)
        return WorkflowSubtitlePipeline().fetch_metadata(source_url)

    def _provider_status(self) -> dict:
        gemini = {"available": True, "code": None, "message": ""}
        if settings.gemini_backend == "agent_platform":
            return {"gemini": gemini}
        row = self.conn.execute(
            """
            SELECT error_code, error_message, finished_at, created_at
            FROM jobs
            WHERE status = 'failed'
              AND (
                error_code = 'GEMINI_QUOTA_EXHAUSTED'
                OR error_message LIKE '%RESOURCE_EXHAUSTED%'
                OR error_message LIKE '%prepayment credits are depleted%'
              )
            ORDER BY COALESCE(finished_at, created_at) DESC, rowid DESC
            LIMIT 1
            """
        ).fetchone()
        if row is not None:
            gemini = {
                "available": False,
                "code": "GEMINI_QUOTA_EXHAUSTED",
                "message": row["error_message"] or row["error_code"] or "",
            }
        return {"gemini": gemini}

    def _write_admin_audit(
        self,
        *,
        actor_user_id: str,
        target_user_id: str,
        minutes: float,
        reason: str,
        created_at: str,
    ) -> None:
        self._write_audit(
            actor_user_id=actor_user_id,
            action="admin_credit_adjustment",
            target_type="user",
            target_id=target_user_id,
            metadata={"minutes": minutes, "reason": reason},
            created_at=created_at,
        )

    def _write_audit(
        self,
        *,
        actor_user_id: str,
        action: str,
        target_type: str,
        target_id: str,
        metadata: dict,
        created_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO admin_audit_logs (
              id, actor_user_id, action, target_type, target_id,
              metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"audit_{uuid4().hex}",
                actor_user_id,
                action,
                target_type,
                target_id,
                json.dumps(metadata, ensure_ascii=False),
                created_at,
            ),
        )


def _validate_public_url(source_url: str) -> None:
    try:
        parsed = urlparse(source_url)
        _ = parsed.port
    except ValueError as exc:
        raise ApiError(400, "INVALID_URL", "Invalid source URL") from exc

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ApiError(400, "INVALID_URL", "Invalid source URL")

    hostname = parsed.hostname.strip().lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ApiError(400, "FORBIDDEN_URL", "Localhost URLs are not allowed")

    try:
        ip = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        if "." not in hostname:
            raise ApiError(400, "FORBIDDEN_URL", "Private hostnames are not allowed")
        return

    if not ip.is_global:
        raise ApiError(400, "FORBIDDEN_URL", "Private IP URLs are not allowed")


def _audit_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["metadata"] = (
        json.loads(item["metadata_json"]) if item.get("metadata_json") else None
    )
    return item


def _event_row(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["metadata"] = (
        json.loads(item["metadata_json"]) if item.get("metadata_json") else None
    )
    return item