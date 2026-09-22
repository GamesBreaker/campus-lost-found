from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('lost', 'found')),
    description TEXT NOT NULL,
    location TEXT,
    happened_at TEXT,
    contact TEXT NOT NULL,
    embedding BLOB NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_provider TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    matched_report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    similarity REAL NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (report_id, matched_report_id)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports(user_id);
CREATE INDEX IF NOT EXISTS idx_reports_kind ON reports(kind);
CREATE INDEX IF NOT EXISTS idx_matches_created_at ON matches(created_at DESC);
"""

_REQUIRED_REPORT_COLUMNS = {
    "id",
    "user_id",
    "kind",
    "description",
    "location",
    "happened_at",
    "contact",
    "embedding",
    "embedding_dim",
    "embedding_provider",
    "embedding_model",
    "created_at",
}


def get_connection() -> sqlite3.Connection:
    db_path: Path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")
        report_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reports)").fetchall()
        }
        if report_columns and not _REQUIRED_REPORT_COLUMNS.issubset(report_columns):
            _drop_legacy_tables(connection)
        connection.executescript(SCHEMA)


def _drop_legacy_tables(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS matches;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS reports;
        DROP TABLE IF EXISTS users;
        """
    )


def reset_db() -> None:
    init_db()
    with get_connection() as connection:
        connection.execute("DELETE FROM matches")
        connection.execute("DELETE FROM sessions")
        connection.execute("DELETE FROM reports")
        connection.execute("DELETE FROM users")
        connection.execute(
            "DELETE FROM sqlite_sequence WHERE name IN ('users', 'sessions', 'reports', 'matches')"
        )


def vector_to_blob(vector: np.ndarray) -> bytes:
    return np.asarray(vector, dtype="<f4").reshape(-1).tobytes()


def blob_to_vector(blob: bytes) -> np.ndarray:
    return np.frombuffer(blob, dtype="<f4").astype(np.float32, copy=True)
