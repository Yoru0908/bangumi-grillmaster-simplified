import unittest
from http.server import HTTPServer, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch


class FakeConnection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeDaemon:
    def __init__(self):
        self.max_iterations = None

    def run_forever(self, *, max_iterations=None):
        self.max_iterations = max_iterations


class FakeServer:
    def __init__(self):
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True

    def server_close(self):
        self.closed = True


class FakeCleanup:
    def __init__(self):
        self.calls = []

    def cleanup_expired_results(self, *, now: str) -> None:
        self.calls.append(("expired", now))

    def cleanup_failed_old_jobs(self, *, job_data_dir, now: str, ttl_hours: int) -> None:
        self.calls.append(("failed", Path(job_data_dir), now, ttl_hours))


class SaasEntrypointTests(unittest.TestCase):
    def test_bootstrap_cli_parses_options_and_closes_connection(self):
        from services.saas import bootstrap_cli

        fake_conn = FakeConnection()
        with (
            patch("services.saas.bootstrap_cli.load_runtime_config") as load_config,
            patch("services.saas.bootstrap_cli.bootstrap_runtime") as bootstrap_runtime,
        ):
            load_config.return_value = "config"
            bootstrap_runtime.return_value = {"connection": fake_conn}

            exit_code = bootstrap_cli.main(
                [
                    "--invite-code",
                    "member-code",
                    "--invite-email",
                    "member@example.com",
                    "--invite-role",
                    "admin",
                    "--initial-credit-minutes",
                    "30",
                    "--now",
                    "2026-01-01T00:00:00Z",
                ]
            )

        self.assertEqual(exit_code, 0)
        bootstrap_runtime.assert_called_once()
        config_arg, options_arg = bootstrap_runtime.call_args.args
        self.assertEqual(config_arg, "config")
        self.assertEqual(options_arg.invite_code, "member-code")
        self.assertEqual(options_arg.invite_email, "member@example.com")
        self.assertEqual(options_arg.invite_role, "admin")
        self.assertEqual(options_arg.initial_credit_minutes, 30)
        self.assertEqual(options_arg.now, "2026-01-01T00:00:00Z")
        self.assertTrue(fake_conn.closed)

    def test_worker_main_runs_daemon_with_worker_id_and_iteration_limit(self):
        from services.saas import worker_main

        daemon = FakeDaemon()
        with (
            patch("services.saas.worker_main.load_runtime_config") as load_config,
            patch("services.saas.worker_main.create_worker_daemon") as create_daemon,
        ):
            load_config.return_value = "config"
            create_daemon.return_value = daemon

            exit_code = worker_main.main(
                ["--worker-id", "worker-test", "--max-iterations", "2"]
            )

        self.assertEqual(exit_code, 0)
        create_daemon.assert_called_once_with("config", worker_id="worker-test")
        self.assertEqual(daemon.max_iterations, 2)

    def test_cleanup_daemon_runs_expired_and_failed_cleanup_once(self):
        from services.saas.cleanup_daemon import CleanupDaemon

        cleanup = FakeCleanup()
        daemon = CleanupDaemon(
            cleanup=cleanup,
            job_data_dir=Path("/tmp/jobs"),
            failed_job_tmp_ttl_hours=12,
            poll_interval_seconds=5,
            now=lambda: "2026-01-02T00:00:00Z",
        )

        daemon.run_once()

        self.assertEqual(
            cleanup.calls,
            [
                ("expired", "2026-01-02T00:00:00Z"),
                ("failed", Path("/tmp/jobs"), "2026-01-02T00:00:00Z", 12),
            ],
        )

    def test_cleanup_main_runs_daemon_with_iteration_limit(self):
        from services.saas import cleanup_daemon

        daemon = FakeDaemon()
        with (
            patch("services.saas.cleanup_daemon.load_runtime_config") as load_config,
            patch("services.saas.cleanup_daemon.create_cleanup_daemon") as create_daemon,
        ):
            load_config.return_value = "config"
            create_daemon.return_value = daemon

            exit_code = cleanup_daemon.main(["--max-iterations", "3"])

        self.assertEqual(exit_code, 0)
        create_daemon.assert_called_once_with("config")
        self.assertEqual(daemon.max_iterations, 3)

    def test_server_main_loads_config_serves_and_closes_server(self):
        from services.saas import server_main

        server = FakeServer()
        with (
            patch("services.saas.server_main.load_runtime_config") as load_config,
            patch("services.saas.server_main.create_http_server") as create_server,
        ):
            load_config.return_value = "config"
            create_server.return_value = server

            exit_code = server_main.main([])

        self.assertEqual(exit_code, 0)
        create_server.assert_called_once_with("config")
        self.assertTrue(server.served)
        self.assertTrue(server.closed)

    def test_create_http_server_uses_single_thread_server_for_sqlite_safety(self):
        from services.saas import server_main
        from services.saas.runtime import RuntimeConfig

        fake_conn = FakeConnection()
        config = RuntimeConfig(
            database_path=Path("/tmp/app.db"),
            job_data_dir=Path("/tmp/jobs"),
            job_result_dir=Path("/tmp/results"),
            log_dir=Path("/tmp/logs"),
            api_host="127.0.0.1",
            api_port=0,
        )
        with (
            patch("services.saas.server_main.connect_database", return_value=fake_conn),
            patch("services.saas.server_main.initialize_database"),
        ):
            server = server_main.create_http_server(config)

        try:
            self.assertIsInstance(server, HTTPServer)
            self.assertNotIsInstance(server, ThreadingHTTPServer)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
