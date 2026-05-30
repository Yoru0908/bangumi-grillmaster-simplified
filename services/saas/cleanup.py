from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4


class CleanupService:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def cleanup_successful_job(
        self,
        job_id: str,
        *,
        job_data_dir: str | Path,
        now: str,
    ) -> None:
        job_dir = Path(job_data_dir) / job_id
        for relative in [
            Path("input"),
            Path("media") / "audio.opus",
            Path("media") / "frames",
            Path("media") / "chunks",
        ]:
            _remove_path(job_dir / relative)

        self.conn.execute(
            """
            UPDATE jobs
            SET stage = 'cleanup_completed',
                progress_message = 'cleanup completed'
            WHERE id = ?
            """,
            (job_id,),
        )
        self._write_event(
            job_id=job_id,
            level="success",
            stage="cleanup_completed",
            code="media_cleaned",
            message="Temporary media files cleaned",
            created_at=now,
        )
        self.conn.commit()

    def cleanup_expired_results(self, *, now: str) -> None:
        rows = self.conn.execute(
            """
            SELECT id, source_srt_path, translated_srt_path, result_srt_path
            FROM jobs
            WHERE status = 'succeeded'
              AND expires_at IS NOT NULL
              AND expires_at <= ?
            """,
            (now,),
        ).fetchall()
        for row in rows:
            for column in ["source_srt_path", "translated_srt_path", "result_srt_path"]:
                if row[column]:
                    _remove_path(Path(row[column]))
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'expired',
                    source_srt_path = NULL,
                    translated_srt_path = NULL,
                    result_srt_path = NULL,
                    progress_message = 'result expired'
                WHERE id = ?
                """,
                (row["id"],),
            )
            self._write_event(
                job_id=row["id"],
                level="info",
                stage="cleanup_completed",
                code="result_expired",
                message="Download result expired and was deleted",
                created_at=now,
            )
        self.conn.commit()

    def cleanup_failed_old_jobs(
        self,
        *,
        job_data_dir: str | Path,
        now: str,
        ttl_hours: int,
    ) -> None:
        threshold = _parse_time(now) - timedelta(hours=ttl_hours)
        rows = self.conn.execute(
            """
            SELECT id, finished_at
            FROM jobs
            WHERE status = 'failed'
              AND finished_at IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            if _parse_time(row["finished_at"]) > threshold:
                continue
            _remove_path(Path(job_data_dir) / row["id"])
            self._write_event(
                job_id=row["id"],
                level="info",
                stage="cleanup_completed",
                code="failed_tmp_cleaned",
                message="Old failed job temporary files cleaned",
                created_at=now,
            )
        self.conn.commit()

    def _write_event(
        self,
        *,
        job_id: str,
        level: str,
        stage: str,
        code: str,
        message: str,
        created_at: str,
        metadata: dict | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO job_events (
              id, job_id, level, stage, code, message, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"event_{uuid4().hex}",
                job_id,
                level,
                stage,
                code,
                message,
                json.dumps(metadata, ensure_ascii=False) if metadata else None,
                created_at,
            ),
        )


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
