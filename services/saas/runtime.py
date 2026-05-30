from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from services.saas.auth import AuthService
from services.saas.credits import CreditLedger
from services.saas.db import connect_database, initialize_database


@dataclass(frozen=True)
class RuntimeConfig:
    database_path: Path
    job_data_dir: Path
    job_result_dir: Path
    log_dir: Path
    api_host: str = "0.0.0.0"
    api_port: int = 8600
    min_submit_credit_minutes: float = 10
    max_video_duration_seconds: int = 3600
    running_job_heartbeat_timeout_seconds: int = 120
    result_ttl_days: int = 14
    failed_job_tmp_ttl_hours: int = 24
    worker_poll_interval_seconds: int = 5


@dataclass(frozen=True)
class BootstrapOptions:
    invite_code: str | None = None
    invite_email: str | None = None
    invite_role: str = "member"
    initial_credit_minutes: float = 0
    now: str = "2026-01-01T00:00:00Z"


def load_runtime_config() -> RuntimeConfig:
    home = Path.home()
    data_root = home / "data" / "bangumi-grillmaster"
    log_root = home / "logs" / "bangumi-grillmaster"
    return RuntimeConfig(
        database_path=Path(
            os.environ.get("SAAS_DATABASE_PATH", data_root / "app.db")
        ),
        job_data_dir=Path(os.environ.get("SAAS_JOB_DATA_DIR", data_root / "jobs")),
        job_result_dir=Path(
            os.environ.get("SAAS_JOB_RESULT_DIR", data_root / "results")
        ),
        log_dir=Path(os.environ.get("SAAS_LOG_DIR", log_root)),
        api_host=os.environ.get("SAAS_API_HOST", "0.0.0.0"),
        api_port=int(os.environ.get("SAAS_API_PORT", "8600")),
        min_submit_credit_minutes=float(
            os.environ.get("SAAS_MIN_SUBMIT_CREDIT_MINUTES", "10")
        ),
        max_video_duration_seconds=int(
            os.environ.get("SAAS_MAX_VIDEO_DURATION_SECONDS", "3600")
        ),
        running_job_heartbeat_timeout_seconds=int(
            os.environ.get("SAAS_RUNNING_JOB_HEARTBEAT_TIMEOUT_SECONDS", "120")
        ),
        result_ttl_days=int(os.environ.get("SAAS_RESULT_TTL_DAYS", "14")),
        failed_job_tmp_ttl_hours=int(
            os.environ.get("SAAS_FAILED_JOB_TMP_TTL_HOURS", "24")
        ),
        worker_poll_interval_seconds=int(
            os.environ.get("SAAS_WORKER_POLL_INTERVAL_SECONDS", "5")
        ),
    )


def bootstrap_runtime(
    config: RuntimeConfig,
    options: BootstrapOptions | None = None,
) -> dict:
    options = options or BootstrapOptions()
    config.database_path.parent.mkdir(parents=True, exist_ok=True)
    config.job_data_dir.mkdir(parents=True, exist_ok=True)
    config.job_result_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)

    conn = connect_database(config.database_path)
    initialize_database(conn)

    if options.invite_code:
        _create_invite_if_missing(conn, options)
    if (
        options.invite_email
        and options.initial_credit_minutes > 0
        and not _has_initial_grant(conn, options)
    ):
        _grant_initial_credits(conn, options)

    return {
        "connection": conn,
        "invite_email": options.invite_email,
        "initial_credit_minutes": options.initial_credit_minutes,
    }


def _create_invite_if_missing(
    conn: sqlite3.Connection,
    options: BootstrapOptions,
) -> None:
    existing = AuthService(conn).get_invite(options.invite_code or "")
    if existing:
        return
    AuthService(conn).create_invite(
        code=options.invite_code or "",
        email=options.invite_email,
        role=options.invite_role,
        created_at=options.now,
        expires_at=None,
    )


def _has_initial_grant(
    conn: sqlite3.Connection,
    options: BootstrapOptions,
) -> bool:
    user_id = _ensure_bootstrap_user(
        conn,
        email=options.invite_email or "",
        now=options.now,
    )
    row = conn.execute(
        """
        SELECT 1 FROM credit_ledger
        WHERE user_id = ? AND reason = 'bootstrap initial credits'
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return row is not None


def _grant_initial_credits(
    conn: sqlite3.Connection,
    options: BootstrapOptions,
) -> None:
    user_id = _ensure_bootstrap_user(
        conn,
        email=options.invite_email or "",
        now=options.now,
    )
    CreditLedger(conn).grant(
        user_id=user_id,
        minutes=options.initial_credit_minutes,
        reason="bootstrap initial credits",
        idempotency_key=f"bootstrap-initial-credits:{options.invite_email}",
        created_at=options.now,
    )


def _ensure_bootstrap_user(conn: sqlite3.Connection, *, email: str, now: str) -> str:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if row:
        return row["id"]
    user_id = f"bootstrap:{email}"
    conn.execute(
        """
        INSERT INTO users (id, email, role, status, created_at, updated_at)
        VALUES (?, ?, 'member', 'active', ?, ?)
        """,
        (user_id, email, now, now),
    )
    conn.commit()
    return user_id
