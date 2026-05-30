from __future__ import annotations

import json
import sqlite3
from uuid import uuid4


class JobNotFound(ValueError):
    pass


class ForbiddenJobAccess(PermissionError):
    pass


class InvalidJobArtifact(ValueError):
    pass


ARTIFACT_COLUMNS = {
    "source.srt": "source_srt_path",
    "translated.srt": "translated_srt_path",
    "finalized.srt": "result_srt_path",
}


class JobAccessService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_jobs_for_user(self, user_id: str) -> list[dict]:
        user = self._get_user(user_id)
        if user["role"] == "admin":
            rows = self.conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_job_for_user(self, job_id: str, user_id: str) -> dict:
        job = self._get_job(job_id)
        user = self._get_user(user_id)
        if job["user_id"] != user_id and user["role"] != "admin":
            raise ForbiddenJobAccess("job does not belong to user")
        return dict(job)

    def get_download_path(
        self,
        job_id: str,
        user_id: str,
        artifact: str,
        *,
        now: str | None = None,
    ) -> str:
        if artifact not in ARTIFACT_COLUMNS:
            raise InvalidJobArtifact(f"unsupported job artifact: {artifact}")

        job = self.get_job_for_user(job_id, user_id)
        column = ARTIFACT_COLUMNS[artifact]
        path = job[column]
        if not path:
            raise InvalidJobArtifact(f"artifact is not available: {artifact}")

        actor = self._get_user(user_id)
        if actor["role"] == "admin" and job["user_id"] != user_id:
            self._write_admin_audit(
                actor_user_id=user_id,
                job_id=job_id,
                artifact=artifact,
                created_at=now or "",
            )
        return path

    def _get_user(self, user_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            "SELECT * FROM users WHERE id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
        if row is None:
            raise ForbiddenJobAccess("active user not found")
        return row

    def _get_job(self, job_id: str) -> sqlite3.Row:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise JobNotFound("job not found")
        return row

    def _write_admin_audit(
        self,
        *,
        actor_user_id: str,
        job_id: str,
        artifact: str,
        created_at: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO admin_audit_logs (
              id, actor_user_id, action, target_type, target_id,
              metadata_json, created_at
            )
            VALUES (?, ?, 'download_job_artifact', 'job', ?, ?, ?)
            """,
            (
                f"audit_{uuid4().hex}",
                actor_user_id,
                job_id,
                json.dumps({"artifact": artifact}, ensure_ascii=False),
                created_at,
            ),
        )
        self.conn.commit()
