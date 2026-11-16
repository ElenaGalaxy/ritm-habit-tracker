"""Работа с SQLite: подключение, инициализация схемы, транзакции."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from flask import current_app, g

BASE_DIR = Path(__file__).resolve().parent.parent
SCHEMA_PATH = BASE_DIR / "schema.sql"


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app) -> None:
    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        conn.executescript(fh.read())
    conn.execute(
        "INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', '1')"
    )
    conn.commit()
    conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def log_error(db: sqlite3.Connection, message: str, path: str = "", method: str = "",
              user_id: int | None = None, level: str = "error") -> None:
    from .utils import iso_now

    try:
        db.execute(
            "INSERT INTO error_logs(user_id, level, message, path, method, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, level, message[:1000], path[:300], method[:10], iso_now()),
        )
        db.commit()
    except sqlite3.Error:
        pass
