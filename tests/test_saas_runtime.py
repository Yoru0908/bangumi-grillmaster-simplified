import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.saas.runtime import (
    BootstrapOptions,
    RuntimeConfig,
    bootstrap_runtime,
    load_runtime_config,
)


class SaasRuntimeTests(unittest.TestCase):
    def test_load_runtime_config_uses_env_and_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {
                "SAAS_DATABASE_PATH": str(root / "app.db"),
                "SAAS_JOB_DATA_DIR": str(root / "jobs"),
                "SAAS_JOB_RESULT_DIR": str(root / "results"),
                "SAAS_LOG_DIR": str(root / "logs"),
                "SAAS_API_HOST": "127.0.0.1",
                "SAAS_API_PORT": "9700",
                "SAAS_MIN_SUBMIT_CREDIT_MINUTES": "15",
                "SAAS_MAX_VIDEO_DURATION_SECONDS": "120",
                "SAAS_RUNNING_JOB_HEARTBEAT_TIMEOUT_SECONDS": "240",
                "SAAS_RESULT_TTL_DAYS": "21",
                "SAAS_FAILED_JOB_TMP_TTL_HOURS": "12",
                "SAAS_WORKER_POLL_INTERVAL_SECONDS": "7",
            }

            with patch.dict(os.environ, env, clear=True):
                config = load_runtime_config()

            self.assertEqual(config.database_path, root / "app.db")
            self.assertEqual(config.job_data_dir, root / "jobs")
            self.assertEqual(config.job_result_dir, root / "results")
            self.assertEqual(config.log_dir, root / "logs")
            self.assertEqual(config.api_host, "127.0.0.1")
            self.assertEqual(config.api_port, 9700)
            self.assertEqual(config.min_submit_credit_minutes, 15)
            self.assertEqual(config.max_video_duration_seconds, 120)
            self.assertEqual(config.running_job_heartbeat_timeout_seconds, 240)
            self.assertEqual(config.result_ttl_days, 21)
            self.assertEqual(config.failed_job_tmp_ttl_hours, 12)
            self.assertEqual(config.worker_poll_interval_seconds, 7)

    def test_bootstrap_runtime_creates_dirs_db_invite_and_initial_credits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RuntimeConfig(
                database_path=root / "app.db",
                job_data_dir=root / "jobs",
                job_result_dir=root / "results",
                log_dir=root / "logs",
            )

            result = bootstrap_runtime(
                config,
                BootstrapOptions(
                    invite_code="member-code",
                    invite_email="member@example.com",
                    invite_role="member",
                    initial_credit_minutes=30,
                    now="2026-01-01T00:00:00Z",
                ),
            )

            self.assertTrue(config.database_path.exists())
            self.assertTrue(config.job_data_dir.is_dir())
            self.assertTrue(config.job_result_dir.is_dir())
            self.assertTrue(config.log_dir.is_dir())
            self.assertEqual(result["invite_email"], "member@example.com")
            self.assertEqual(result["initial_credit_minutes"], 30)

            conn = result["connection"]
            invite = conn.execute("SELECT * FROM invite_codes").fetchone()
            ledger = conn.execute("SELECT * FROM credit_ledger").fetchone()
            balance = conn.execute("SELECT * FROM credit_balances").fetchone()

            self.assertEqual(invite["email"], "member@example.com")
            self.assertEqual(invite["role"], "member")
            self.assertEqual(ledger["type"], "grant")
            self.assertEqual(ledger["minutes"], 30)
            self.assertEqual(balance["balance_minutes"], 30)
            conn.close()

    def test_bootstrap_runtime_is_idempotent_for_existing_invite_and_grant(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RuntimeConfig(
                database_path=root / "app.db",
                job_data_dir=root / "jobs",
                job_result_dir=root / "results",
                log_dir=root / "logs",
            )
            options = BootstrapOptions(
                invite_code="member-code",
                invite_email="member@example.com",
                invite_role="member",
                initial_credit_minutes=30,
                now="2026-01-01T00:00:00Z",
            )

            first = bootstrap_runtime(config, options)
            first["connection"].close()
            second = bootstrap_runtime(config, options)

            conn = second["connection"]
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM invite_codes").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM credit_ledger").fetchone()[0], 1)
            self.assertEqual(
                conn.execute("SELECT balance_minutes FROM credit_balances").fetchone()[0],
                30,
            )
            conn.close()


if __name__ == "__main__":
    unittest.main()
