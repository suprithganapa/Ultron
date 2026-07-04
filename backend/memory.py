"""
Persistent memory for ULTRON.

Works with two backends, chosen automatically:
  * SQLite (default) — zero-config, great for local use.
  * Postgres (when DATABASE_URL is set) — durable memory for cloud hosting,
    so ULTRON never forgets across deploys/restarts.

Stores conversation history plus personal-ops data (notes, tasks, reminders).
Only stdlib sqlite3 is needed for local; psycopg is used only if a Postgres
URL is configured.
"""
from __future__ import annotations

import sqlite3
import time
from typing import Any

from .config import settings

IS_PG = settings.database_url.startswith(("postgres://", "postgresql://"))

if IS_PG:
    import psycopg  # type: ignore

    def _connect():
        return psycopg.connect(settings.database_url)

    PH = "%s"       # parameter placeholder
    SERIAL = "SERIAL PRIMARY KEY"
else:
    def _connect():
        c = sqlite3.connect(settings.db_path)
        c.row_factory = sqlite3.Row
        return c

    PH = "?"
    SERIAL = "INTEGER PRIMARY KEY AUTOINCREMENT"


def _q(sql: str) -> str:
    """Rewrite '?' placeholders to the active backend's style."""
    return sql.replace("?", PH) if IS_PG else sql


def init_db() -> None:
    stmts = [
        f"""CREATE TABLE IF NOT EXISTS messages (
            id {SERIAL}, session TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, ts DOUBLE PRECISION NOT NULL)""".replace(
            "DOUBLE PRECISION", "REAL" if not IS_PG else "DOUBLE PRECISION"),
        f"""CREATE TABLE IF NOT EXISTS notes (
            id {SERIAL}, text TEXT NOT NULL, tag TEXT DEFAULT '',
            ts {'DOUBLE PRECISION' if IS_PG else 'REAL'} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS tasks (
            id {SERIAL}, title TEXT NOT NULL, done INTEGER DEFAULT 0,
            ts {'DOUBLE PRECISION' if IS_PG else 'REAL'} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS reminders (
            id {SERIAL}, text TEXT NOT NULL,
            due {'DOUBLE PRECISION' if IS_PG else 'REAL'} NOT NULL,
            fired INTEGER DEFAULT 0,
            ts {'DOUBLE PRECISION' if IS_PG else 'REAL'} NOT NULL)""",
    ]
    with _connect() as c:
        cur = c.cursor()
        for s in stmts:
            cur.execute(s)
        c.commit()


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _insert_returning(sql: str, params: tuple) -> int:
    """Insert and return the new row id, portably."""
    with _connect() as c:
        cur = c.cursor()
        if IS_PG:
            cur.execute(_q(sql) + " RETURNING id", params)
            new_id = cur.fetchone()[0]
        else:
            cur.execute(_q(sql), params)
            new_id = cur.lastrowid
        c.commit()
        return int(new_id)


# ----------------------- conversation history -----------------------

def add_message(session: str, role: str, content: str) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(
            _q("INSERT INTO messages (session, role, content, ts) VALUES (?,?,?,?)"),
            (session, role, content, time.time()),
        )
        c.commit()


def get_history(session: str, limit: int = 40) -> list[dict[str, str]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(
            _q("SELECT role, content FROM messages WHERE session=? "
               "ORDER BY id DESC LIMIT ?"),
            (session, limit),
        )
        rows = _rows(cur)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_history(session: str) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM messages WHERE session=?"), (session,))
        c.commit()


# ----------------------------- notes --------------------------------

def add_note(text: str, tag: str = "") -> int:
    return _insert_returning(
        "INSERT INTO notes (text, tag, ts) VALUES (?,?,?)", (text, tag, time.time()))


def list_notes() -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT id, text, tag, ts FROM notes ORDER BY id DESC")
        return _rows(cur)


def delete_note(note_id: int) -> bool:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM notes WHERE id=?"), (note_id,))
        c.commit()
        return cur.rowcount > 0


# ----------------------------- tasks --------------------------------

def add_task(title: str) -> int:
    return _insert_returning(
        "INSERT INTO tasks (title, done, ts) VALUES (?,0,?)", (title, time.time()))


def list_tasks() -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT id, title, done, ts FROM tasks ORDER BY done, id DESC")
        return _rows(cur)


def complete_task(task_id: int) -> bool:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE tasks SET done=1 WHERE id=?"), (task_id,))
        c.commit()
        return cur.rowcount > 0


# --------------------------- reminders ------------------------------

def add_reminder(text: str, due_epoch: float) -> int:
    return _insert_returning(
        "INSERT INTO reminders (text, due, fired, ts) VALUES (?,?,0,?)",
        (text, due_epoch, time.time()))


def list_reminders() -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT id, text, due, fired, ts FROM reminders ORDER BY due")
        return _rows(cur)


def due_reminders() -> list[dict[str, Any]]:
    now = time.time()
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT id, text, due, fired, ts FROM reminders "
                       "WHERE fired=0 AND due<=?"), (now,))
        rows = _rows(cur)
        for r in rows:
            cur.execute(_q("UPDATE reminders SET fired=1 WHERE id=?"), (r["id"],))
        c.commit()
    return rows
