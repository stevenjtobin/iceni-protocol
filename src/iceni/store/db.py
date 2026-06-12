"""Connection + forward-only migrations (tracked via PRAGMA user_version)."""
from __future__ import annotations

import sqlite3
from importlib.resources import files

from .. import config

LATEST = 3

_MIGRATIONS = {
    1: "sql/0001_init.sql",
    2: "sql/0002_exec_feedback.sql",
    3: "sql/0003_edit_signal.sql",
}


def connect() -> sqlite3.Connection:
    config.ensure_home()
    conn = sqlite3.connect(config.db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Forward-only migrations tracked via PRAGMA user_version."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target in range(version + 1, LATEST + 1):
        sql = files("iceni").joinpath(_MIGRATIONS[target]).read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.execute(f"PRAGMA user_version = {target}")
        conn.commit()
