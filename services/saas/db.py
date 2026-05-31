from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  role TEXT NOT NULL CHECK (role IN ('member', 'admin')),
  status TEXT NOT NULL CHECK (status IN ('active', 'disabled')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invite_codes (
  code_hash TEXT PRIMARY KEY,
  email TEXT,
  role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
  used_by_user_id TEXT REFERENCES users(id),
  used_at TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  job_type TEXT NOT NULL DEFAULT 'paid' CHECK (job_type IN ('paid', 'trial')),
  source_url TEXT NOT NULL,
  source_url_redacted TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'retrying', 'succeeded', 'failed', 'cancelled', 'expired')),
  stage TEXT NOT NULL CHECK (stage IN ('created', 'metadata_fetched', 'video_downloaded', 'audio_extracted', 'asr_completed', 'prepass_completed', 'translated', 'structure_fixed', 'finalized', 'cleanup_completed')),
  current_chunk_index INTEGER NOT NULL DEFAULT 0,
  total_chunks INTEGER NOT NULL DEFAULT 0,
  progress_message TEXT,
  error_code TEXT,
  error_message TEXT,
  video_title TEXT,
  video_duration_seconds INTEGER,
  reserved_minutes REAL NOT NULL DEFAULT 0,
  consumed_minutes REAL NOT NULL DEFAULT 0,
  worker_id TEXT,
  heartbeat_at TEXT,
  source_srt_path TEXT,
  translated_srt_path TEXT,
  result_srt_path TEXT,
  log_path TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  retry_after_seconds INTEGER,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  expires_at TEXT
);

CREATE TABLE IF NOT EXISTS job_events (
  id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  level TEXT NOT NULL CHECK (level IN ('info', 'warning', 'error', 'success')),
  stage TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_balances (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  balance_minutes REAL NOT NULL CHECK (balance_minutes >= 0),
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credit_ledger (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  job_id TEXT REFERENCES jobs(id),
  type TEXT NOT NULL CHECK (type IN ('grant', 'reserve', 'consume', 'refund', 'adjustment')),
  minutes REAL NOT NULL CHECK (minutes > 0),
  reason TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  created_by_user_id TEXT REFERENCES users(id),
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
  id TEXT PRIMARY KEY,
  actor_user_id TEXT NOT NULL REFERENCES users(id),
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_worker_heartbeat ON jobs(worker_id, heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_job_events_job_created ON job_events(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created ON credit_ledger(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_audit_target ON admin_audit_logs(target_type, target_id, created_at DESC);
"""


def connect_database(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def initialize_database(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass  # already set by another connection
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    _ensure_jobs_job_type_column(conn)
    conn.commit()


def _ensure_jobs_job_type_column(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    if "job_type" not in columns:
        conn.execute(
            """
            ALTER TABLE jobs
            ADD COLUMN job_type TEXT NOT NULL DEFAULT 'paid'
            CHECK (job_type IN ('paid', 'trial'))
            """
        )