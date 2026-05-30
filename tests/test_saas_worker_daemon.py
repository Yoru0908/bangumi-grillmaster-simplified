import unittest
from pathlib import Path
from unittest.mock import patch

from services.saas.runtime import RuntimeConfig
from services.saas.worker_daemon import WorkerDaemon, create_worker_daemon


class FakeWorker:
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def run_once(self, *, now: str) -> bool:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return False


class FakeSleeper:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds: int) -> None:
        self.calls.append(seconds)


class FakeClock:
    def __init__(self):
        self.tick = 0

    def __call__(self) -> str:
        self.tick += 1
        return f"2026-01-01T00:00:0{self.tick}Z"


class WorkerDaemonTests(unittest.TestCase):
    def test_run_forever_processes_until_max_iterations_without_sleep_after_work(self):
        worker = FakeWorker([True, False, False])
        sleeper = FakeSleeper()
        daemon = WorkerDaemon(
            worker=worker,
            poll_interval_seconds=5,
            sleep=sleeper,
            now=FakeClock(),
        )

        daemon.run_forever(max_iterations=3)

        self.assertEqual(worker.calls, 3)
        self.assertEqual(sleeper.calls, [5, 5])

    def test_run_forever_stops_when_stop_condition_is_true(self):
        worker = FakeWorker([False, False, False])
        sleeper = FakeSleeper()
        calls = {"count": 0}

        def stop_condition() -> bool:
            calls["count"] += 1
            return calls["count"] > 2

        daemon = WorkerDaemon(
            worker=worker,
            poll_interval_seconds=3,
            sleep=sleeper,
            now=FakeClock(),
            stop_condition=stop_condition,
        )

        daemon.run_forever()

        self.assertEqual(worker.calls, 2)
        self.assertEqual(sleeper.calls, [3, 3])

    def test_create_worker_daemon_wires_runtime_config_to_real_worker(self):
        config = RuntimeConfig(
            database_path=Path("/tmp/app.db"),
            job_data_dir=Path("/tmp/jobs"),
            job_result_dir=Path("/tmp/results"),
            log_dir=Path("/tmp/logs"),
            worker_poll_interval_seconds=9,
            max_video_duration_seconds=123,
            running_job_heartbeat_timeout_seconds=456,
        )

        with (
            patch("services.saas.worker_daemon.connect_database") as connect_database,
            patch("services.saas.worker_daemon.initialize_database") as initialize_database,
            patch("services.saas.worker_daemon.JobStore") as job_store_class,
            patch(
                "services.saas.worker_daemon._utc_now",
                return_value="2026-01-01T00:10:00Z",
            ),
        ):
            connect_database.return_value = "conn"
            daemon = create_worker_daemon(config, worker_id="worker-test")

        connect_database.assert_called_once_with(Path("/tmp/app.db"))
        initialize_database.assert_called_once_with("conn")
        job_store_class.assert_called_once_with("conn")
        job_store_class.return_value.recover_stale_running_jobs.assert_called_once_with(
            now="2026-01-01T00:10:00Z",
            heartbeat_timeout_seconds=456,
        )
        self.assertEqual(daemon.poll_interval_seconds, 9)
        self.assertEqual(daemon.worker.worker_id, "worker-test")
        self.assertEqual(daemon.worker.job_data_dir, Path("/tmp/jobs"))
        self.assertEqual(daemon.worker.max_video_duration_seconds, 123)


if __name__ == "__main__":
    unittest.main()
