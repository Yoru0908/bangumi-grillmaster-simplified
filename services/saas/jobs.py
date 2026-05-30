from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4


class JobStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_job(
        self,
        *,
        user_id: str,
        source_url: str,
        now: str,
        job_type: str = "paid",
        video_title: str | None = None,
        video_duration_seconds: int | None = None,
    ) -> str:
        job_id = f"job_{uuid4().hex}"
        self.conn.execute(
            """
            INSERT INTO jobs (
              id, user_id, job_type, source_url, source_url_redacted,
              status, stage, video_title, video_duration_seconds, created_at
            )
            VALUES (?, ?, ?, ?, ?, 'queued', 'created', ?, ?, ?)
            """,
            (
                job_id,
                user_id,
                job_type,
                source_url,
                redact_url(source_url),
                video_title,
                video_duration_seconds,
                now,
            ),
        )
        self.conn.commit()
        return job_id

    def create_anonymous_trial_job(self, *, source_url: str, now: str) -> str:
        """Create a trial job without a logged-in user."""
        user_id = "anon_trial"
        self._ensure_anon_user(now)
        return self.create_job(
            user_id=user_id,
            source_url=source_url,
            now=now,
            job_type="trial",
        )

    def _ensure_anon_user(self, now: str) -> None:
        row = self.conn.execute(
            "SELECT 1 FROM users WHERE id = 'anon_trial'"
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO users (id, email, role, status, created_at, updated_at) VALUES ('anon_trial', 'anon@trial.local', 'member', 'active', ?, ?)",
                (now, now),
            )
            self.conn.commit()

    def claim_next(self, *, worker_id: str, now: str) -> dict | None:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                """
                SELECT id
                FROM jobs
                WHERE status = 'queued'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ).fetchone()
            if row is None:
                self.conn.commit()
                return None

            job_id = row["id"]
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    worker_id = ?,
                    heartbeat_at = ?,
                    started_at = ?
                WHERE id = ? AND status = 'queued'
                """,
                (worker_id, now, now, job_id),
            )
            claimed = self.conn.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        except Exception:
            self.conn.rollback()
            raise
        self.conn.commit()
        return dict(claimed) if claimed is not None else None

    def recover_stale_running_jobs(
        self,
        *,
        now: str,
        heartbeat_timeout_seconds: int,
    ) -> list[str]:
        threshold = _parse_time(now) - timedelta(seconds=heartbeat_timeout_seconds)
        rows = self.conn.execute(
            """
            SELECT id, stage, heartbeat_at
            FROM jobs
            WHERE status = 'running'
              AND heartbeat_at IS NOT NULL
            """
        ).fetchall()
        recovered: list[str] = []
        for row in rows:
            if _parse_time(row["heartbeat_at"]) > threshold:
                continue
            job_id = row["id"]
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'queued',
                    progress_message = 'requeued after stale worker heartbeat',
                    worker_id = NULL,
                    heartbeat_at = NULL,
                    started_at = NULL,
                    retry_count = retry_count + 1
                WHERE id = ?
                """,
                (job_id,),
            )
            self.conn.execute(
                """
                INSERT INTO job_events (
                  id, job_id, level, stage, code, message, metadata_json, created_at
                )
                VALUES (?, ?, 'warning', ?, 'stale_running_requeued', ?, ?, ?)
                """,
                (
                    f"event_{uuid4().hex}",
                    job_id,
                    row["stage"],
                    "Running job was requeued after stale worker heartbeat",
                    json.dumps(
                        {
                            "heartbeat_at": row["heartbeat_at"],
                            "heartbeat_timeout_seconds": heartbeat_timeout_seconds,
                        },
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )
            recovered.append(job_id)
        self.conn.commit()
        return recovered


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))