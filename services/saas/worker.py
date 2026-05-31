from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from uuid import uuid4

from services.saas.cleanup import CleanupService
from services.saas.credits import CreditLedger, InsufficientCredits
from services.saas.api_service import ApiError, _validate_public_url
from services.saas.jobs import JobStore
from services.saas.pipeline import PipelineError, PipelineMetadata, SubtitlePipeline


class SingleJobWorker:
    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        worker_id: str,
        pipeline: SubtitlePipeline,
        job_data_dir: str | Path | None = None,
        max_video_duration_seconds: int = 3600,
    ):
        self.conn = conn
        self.worker_id = worker_id
        self.pipeline = pipeline
        self.job_data_dir = Path(job_data_dir) if job_data_dir is not None else None
        self.max_video_duration_seconds = max_video_duration_seconds

    def run_once(self, *, now: str) -> bool:
        claimed = JobStore(self.conn).claim_next(worker_id=self.worker_id, now=now)
        if claimed is None:
            return False

        job_id = claimed["id"]
        source_url = claimed["source_url"]
        user_id = claimed["user_id"]
        is_trial = claimed.get("job_type") == "trial"

        is_upload = source_url.startswith("upload://")

        try:
            if not is_upload:
                _validate_public_url(source_url)
        except ApiError as exc:
            self._mark_failed(
                job_id=job_id,
                error_code=exc.code,
                error_message=exc.message,
                now=now,
            )
            return True

        try:
            if not is_upload:
                metadata = self.pipeline.fetch_metadata(source_url)
        except PipelineError as exc:
            self._mark_failed(
                job_id=job_id,
                error_code=exc.code,
                error_message=exc.message,
                now=now,
            )
            return True

        if is_upload:
            metadata = PipelineMetadata(
                video_title=source_url.replace("upload://", ""),
                video_duration_seconds=600,  # 10 min default, adjusted after processing
            )
            # Update job with metadata
            self._mark_metadata_fetched(
                job_id=job_id,
                title=metadata.video_title,
                duration_seconds=metadata.video_duration_seconds,
                now=now,
            )

        duration_minutes = _duration_minutes(metadata.video_duration_seconds)
        self._mark_metadata_fetched(
            job_id=job_id,
            title=metadata.video_title,
            duration_seconds=metadata.video_duration_seconds,
            now=now,
        )

        if (
            not is_trial
            and metadata.video_duration_seconds > self.max_video_duration_seconds
        ):
            self._mark_failed(
                job_id=job_id,
                error_code="VIDEO_TOO_LONG",
                error_message="Video exceeds maximum duration",
                now=now,
            )
            return True

        if is_trial and metadata.video_duration_seconds > 60:
            self._mark_failed(
                job_id=job_id,
                error_code="TRIAL_VIDEO_TOO_LONG",
                error_message="Trial jobs are limited to 60 seconds",
                now=now,
            )
            return True

        if not is_trial:
            try:
                CreditLedger(self.conn).reserve(
                    user_id=user_id,
                    job_id=job_id,
                    minutes=duration_minutes,
                    idempotency_key=f"reserve:{job_id}",
                    created_at=now,
                )
            except InsufficientCredits as exc:
                self._mark_failed(
                    job_id=job_id,
                    error_code="INSUFFICIENT_CREDITS",
                    error_message=str(exc),
                    now=now,
                )
                return True

        try:
            def _on_stage(stage, msg):
                try:
                    self.conn.execute(
                        "UPDATE jobs SET stage=?, progress_message=?, heartbeat_at=? WHERE id=?",
                        (stage, msg, self._now(), job_id),
                    )
                    self.conn.commit()
                except Exception:
                    pass
            result = self.pipeline.run(
                job_id=job_id, source_url=source_url, on_stage_change=_on_stage,
                job_data_dir=str(self.job_data_dir),
            )
        except PipelineError as exc:
            if not is_trial:
                CreditLedger(self.conn).refund(
                    user_id=user_id,
                    job_id=job_id,
                    minutes=duration_minutes,
                    idempotency_key=f"refund:{job_id}",
                    created_at=now,
                )
            self._mark_failed(
                job_id=job_id,
                error_code=exc.code,
                error_message=exc.message,
                now=now,
            )
            return True

        if not is_trial:
            CreditLedger(self.conn).consume(
                user_id=user_id,
                job_id=job_id,
                minutes=duration_minutes,
                idempotency_key=f"consume:{job_id}",
                created_at=now,
            )
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'succeeded',
                stage = 'cleanup_completed',
                source_srt_path = ?,
                translated_srt_path = ?,
                result_srt_path = ?,
                finished_at = ?,
                progress_message = 'completed'
            WHERE id = ?
            """,
            (
                result.source_srt_path,
                result.translated_srt_path,
                result.finalized_srt_path,
                now,
                job_id,
            ),
        )
        self._write_event(
            job_id=job_id,
            level="success",
            stage="cleanup_completed",
            code="job_succeeded",
            message="Job completed",
            metadata=None,
            created_at=now,
        )
        self.conn.commit()
        if self.job_data_dir is not None:
            CleanupService(self.conn).cleanup_successful_job(
                job_id,
                job_data_dir=self.job_data_dir,
                now=now,
            )
        return True

    def _mark_metadata_fetched(
        self,
        *,
        job_id: str,
        title: str,
        duration_seconds: int,
        now: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE jobs
            SET stage = 'metadata_fetched',
                video_title = ?,
                video_duration_seconds = ?,
                progress_message = 'metadata fetched'
            WHERE id = ?
            """,
            (title, duration_seconds, job_id),
        )
        self._write_event(
            job_id=job_id,
            level="info",
            stage="metadata_fetched",
            code="metadata_fetched",
            message="Metadata fetched",
            metadata={"video_title": title, "video_duration_seconds": duration_seconds},
            created_at=now,
        )
        self.conn.commit()

    def _mark_failed(
        self,
        *,
        job_id: str,
        error_code: str,
        error_message: str,
        now: str,
    ) -> None:
        self.conn.execute(
            """
            UPDATE jobs
            SET status = 'failed',
                error_code = ?,
                error_message = ?,
                finished_at = ?,
                progress_message = 'failed'
            WHERE id = ?
            """,
            (error_code, error_message, now, job_id),
        )
        self._write_event(
            job_id=job_id,
            level="error",
            stage=self._current_stage(job_id),
            code=error_code,
            message=error_message,
            metadata=None,
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
        metadata: dict | None,
        created_at: str,
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

    def _current_stage(self, job_id: str) -> str:
        row = self.conn.execute("SELECT stage FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row["stage"]


def _duration_minutes(duration_seconds: int) -> int:
    return max(1, math.ceil(duration_seconds / 60))