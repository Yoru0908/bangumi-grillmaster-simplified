from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable, Protocol

from services.saas.db import connect_database, initialize_database
from services.saas.jobs import JobStore
from services.saas.pipeline import WorkflowSubtitlePipeline
from services.saas.runtime import RuntimeConfig
from services.saas.worker import SingleJobWorker


class RunnableWorker(Protocol):
    def run_once(self, *, now: str) -> bool:
        raise NotImplementedError


class WorkerDaemon:
    def __init__(
        self,
        *,
        worker: RunnableWorker,
        poll_interval_seconds: int,
        sleep: Callable[[int], None] = time.sleep,
        now: Callable[[], str] | None = None,
        stop_condition: Callable[[], bool] | None = None,
    ):
        self.worker = worker
        self.poll_interval_seconds = poll_interval_seconds
        self.sleep = sleep
        self.now = now or _utc_now
        self.stop_condition = stop_condition

    def run_forever(self, *, max_iterations: int | None = None) -> None:
        iterations = 0
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                return
            if self.stop_condition is not None and self.stop_condition():
                return

            processed = self.worker.run_once(now=self.now())
            iterations += 1
            if not processed:
                self.sleep(self.poll_interval_seconds)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def create_worker_daemon(
    config: RuntimeConfig,
    *,
    worker_id: str,
) -> WorkerDaemon:
    conn = connect_database(config.database_path)
    initialize_database(conn)
    worker = SingleJobWorker(
        conn,
        worker_id=worker_id,
        pipeline=WorkflowSubtitlePipeline(),
        job_data_dir=config.job_data_dir,
        max_video_duration_seconds=config.max_video_duration_seconds,
    )
    JobStore(conn).recover_stale_running_jobs(
        now=_utc_now(),
        heartbeat_timeout_seconds=config.running_job_heartbeat_timeout_seconds,
    )
    return WorkerDaemon(
        worker=worker,
        poll_interval_seconds=config.worker_poll_interval_seconds,
    )
