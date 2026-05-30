from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Callable, Protocol

from services.saas.cleanup import CleanupService
from services.saas.db import connect_database, initialize_database
from services.saas.runtime import RuntimeConfig, load_runtime_config
from services.saas.worker_daemon import _utc_now


class RunnableCleanup(Protocol):
    def cleanup_expired_results(self, *, now: str) -> None:
        raise NotImplementedError

    def cleanup_failed_old_jobs(
        self,
        *,
        job_data_dir: str | Path,
        now: str,
        ttl_hours: int,
    ) -> None:
        raise NotImplementedError


class CleanupDaemon:
    def __init__(
        self,
        *,
        cleanup: RunnableCleanup,
        job_data_dir: str | Path,
        failed_job_tmp_ttl_hours: int,
        poll_interval_seconds: int,
        sleep: Callable[[int], None] = time.sleep,
        now: Callable[[], str] | None = None,
        stop_condition: Callable[[], bool] | None = None,
    ):
        self.cleanup = cleanup
        self.job_data_dir = Path(job_data_dir)
        self.failed_job_tmp_ttl_hours = failed_job_tmp_ttl_hours
        self.poll_interval_seconds = poll_interval_seconds
        self.sleep = sleep
        self.now = now or _utc_now
        self.stop_condition = stop_condition

    def run_once(self) -> None:
        now = self.now()
        self.cleanup.cleanup_expired_results(now=now)
        self.cleanup.cleanup_failed_old_jobs(
            job_data_dir=self.job_data_dir,
            now=now,
            ttl_hours=self.failed_job_tmp_ttl_hours,
        )

    def run_forever(self, *, max_iterations: int | None = None) -> None:
        iterations = 0
        while True:
            if max_iterations is not None and iterations >= max_iterations:
                return
            if self.stop_condition is not None and self.stop_condition():
                return

            self.run_once()
            iterations += 1
            if max_iterations is None or iterations < max_iterations:
                self.sleep(self.poll_interval_seconds)


def create_cleanup_daemon(config: RuntimeConfig) -> CleanupDaemon:
    conn = connect_database(config.database_path)
    initialize_database(conn)
    return CleanupDaemon(
        cleanup=CleanupService(conn),
        job_data_dir=config.job_data_dir,
        failed_job_tmp_ttl_hours=config.failed_job_tmp_ttl_hours,
        poll_interval_seconds=config.worker_poll_interval_seconds,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the SaaS cleanup daemon")
    parser.add_argument("--max-iterations", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    create_cleanup_daemon(load_runtime_config()).run_forever(
        max_iterations=args.max_iterations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
