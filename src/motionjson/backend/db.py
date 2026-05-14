from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TEXT NOT NULL,
    disabled_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    kind TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    uri TEXT NOT NULL,
    content_type TEXT,
    byte_size INTEGER NOT NULL,
    source_job_id TEXT REFERENCES jobs(id),
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    created_by_user_id TEXT NOT NULL REFERENCES users(id),
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    result_json TEXT NOT NULL,
    error TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS queue_items (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
    status TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    run_after TEXT NOT NULL,
    locked_by TEXT,
    locked_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id),
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usage_events (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    project_id TEXT REFERENCES projects(id),
    job_id TEXT REFERENCES jobs(id),
    event_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rights_metadata (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    asset_id TEXT REFERENCES assets(id),
    object_id TEXT,
    job_id TEXT REFERENCES jobs(id),
    rights_json TEXT NOT NULL,
    creator_approved INTEGER NOT NULL DEFAULT 0,
    creator_approval_status TEXT NOT NULL,
    commercial_use INTEGER NOT NULL DEFAULT 0,
    commercial_use_status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset_lineage (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects(id),
    source_asset_id TEXT REFERENCES assets(id),
    derived_asset_id TEXT NOT NULL REFERENCES assets(id),
    job_id TEXT REFERENCES jobs(id),
    operation TEXT NOT NULL,
    object_id TEXT,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id),
    project_id TEXT REFERENCES projects(id),
    job_id TEXT REFERENCES jobs(id),
    asset_id TEXT REFERENCES assets(id),
    object_id TEXT,
    event_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_user_id, archived_at);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_assets_source_job ON assets(source_job_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_queue_claim ON queue_items(status, run_after, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_usage_project ON usage_events(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_rights_asset ON rights_metadata(asset_id, object_id);
CREATE INDEX IF NOT EXISTS idx_rights_project ON rights_metadata(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_lineage_source ON asset_lineage(source_asset_id);
CREATE INDEX IF NOT EXISTS idx_lineage_derived ON asset_lineage(derived_asset_id);
CREATE INDEX IF NOT EXISTS idx_audit_scope ON audit_events(project_id, job_id, asset_id, created_at);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def initialize_database(path_or_conn: str | Path | sqlite3.Connection) -> sqlite3.Connection:
    if isinstance(path_or_conn, sqlite3.Connection):
        conn = path_or_conn
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    else:
        conn = connect(path_or_conn)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
