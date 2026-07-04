"""
Persistent, multi-user memory for ULTRON.

Backends (chosen automatically):
  * SQLite (default) — zero-config local use.
  * Postgres (DATABASE_URL set) — durable cloud memory.

Everything is scoped per user: accounts, conversations, messages, notes,
tasks, reminders, and profiles. This is what turns ULTRON into a real
multi-user platform where each person's data is isolated.
"""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any

from .config import settings

IS_PG = settings.database_url.startswith(("postgres://", "postgresql://"))

if IS_PG:
    import psycopg  # type: ignore

    def _connect():
        return psycopg.connect(settings.database_url)

    PH, SERIAL, REAL = "%s", "SERIAL PRIMARY KEY", "DOUBLE PRECISION"
else:
    def _connect():
        c = sqlite3.connect(settings.db_path)
        c.row_factory = sqlite3.Row
        return c

    PH, SERIAL, REAL = "?", "INTEGER PRIMARY KEY AUTOINCREMENT", "REAL"


def _q(sql: str) -> str:
    return sql.replace("?", PH) if IS_PG else sql


def _has_column(cur, table: str, column: str) -> bool:
    """True if `table` exists and has `column` (portable across backends)."""
    try:
        if IS_PG:
            cur.execute("SELECT 1 FROM information_schema.columns "
                        "WHERE table_name=%s AND column_name=%s", (table, column))
            return cur.fetchone() is not None
        cur.execute(f"PRAGMA table_info({table})")
        return any(r[1] == column for r in cur.fetchall())
    except Exception:
        return False


def init_db() -> None:
    # Migration: a pre-v2 (single-user) database has messages/notes/tasks/
    # reminders tables WITHOUT the per-user columns. CREATE TABLE IF NOT EXISTS
    # would leave the old schema in place, so drop those stale tables first.
    # (Their pre-multi-user data is disposable; accounts/conversations are new.)
    with _connect() as c:
        cur = c.cursor()
        for table, col in [("messages", "conversation_id"), ("notes", "user_id"),
                           ("tasks", "user_id"), ("reminders", "user_id")]:
            if not _has_column(cur, table, col):
                cur.execute(f"DROP TABLE IF EXISTS {table}")
        c.commit()

    stmts = [
        f"""CREATE TABLE IF NOT EXISTS users (
            id {SERIAL}, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0, disabled INTEGER DEFAULT 0,
            created {REAL} NOT NULL, last_active {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS conversations (
            id {SERIAL}, user_id INTEGER NOT NULL, title TEXT DEFAULT 'New chat',
            created {REAL} NOT NULL, updated {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS messages (
            id {SERIAL}, conversation_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, ts {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS notes (
            id {SERIAL}, user_id INTEGER NOT NULL, text TEXT NOT NULL,
            tag TEXT DEFAULT '', ts {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS tasks (
            id {SERIAL}, user_id INTEGER NOT NULL, title TEXT NOT NULL,
            done INTEGER DEFAULT 0, ts {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS reminders (
            id {SERIAL}, user_id INTEGER NOT NULL, text TEXT NOT NULL,
            due {REAL} NOT NULL, fired INTEGER DEFAULT 0, ts {REAL} NOT NULL)""",
        f"""CREATE TABLE IF NOT EXISTS profiles (
            user_id INTEGER PRIMARY KEY, data TEXT NOT NULL)""",
    ]
    with _connect() as c:
        cur = c.cursor()
        for s in stmts:
            cur.execute(s)
        c.commit()


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _one(cur) -> dict[str, Any] | None:
    row = cur.fetchone()
    if row is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _insert_returning(sql: str, params: tuple) -> int:
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


# ------------------------------- users ------------------------------

def create_user(email: str, password_hash: str, is_admin: bool = False) -> int | None:
    now = time.time()
    try:
        return _insert_returning(
            "INSERT INTO users (email, password_hash, is_admin, disabled, created, "
            "last_active) VALUES (?,?,?,0,?,?)",
            (email.lower(), password_hash, 1 if is_admin else 0, now, now),
        )
    except Exception:
        return None  # duplicate email


def get_user_by_email(email: str) -> dict[str, Any] | None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT * FROM users WHERE email=?"), (email.lower(),))
        return _one(cur)


def get_user(user_id: int) -> dict[str, Any] | None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT * FROM users WHERE id=?"), (user_id,))
        return _one(cur)


def touch_user(user_id: int) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE users SET last_active=? WHERE id=?"),
                    (time.time(), user_id))
        c.commit()


def list_users() -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT id, email, is_admin, disabled, created, last_active "
                    "FROM users ORDER BY id")
        return _rows(cur)


def set_user_disabled(user_id: int, disabled: bool) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE users SET disabled=? WHERE id=?"),
                    (1 if disabled else 0, user_id))
        c.commit()


def delete_user(user_id: int) -> None:
    with _connect() as c:
        cur = c.cursor()
        for t in ("messages", "conversations", "notes", "tasks", "reminders",
                  "profiles"):
            cur.execute(_q(f"DELETE FROM {t} WHERE user_id=?"), (user_id,))
        cur.execute(_q("DELETE FROM users WHERE id=?"), (user_id,))
        c.commit()


def count_users() -> int:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        return int(cur.fetchone()[0])


# --------------------------- conversations --------------------------

def create_conversation(user_id: int, title: str = "New chat") -> int:
    now = time.time()
    return _insert_returning(
        "INSERT INTO conversations (user_id, title, created, updated) "
        "VALUES (?,?,?,?)", (user_id, title, now, now))


def list_conversations(user_id: int) -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT id, title, created, updated FROM conversations "
                       "WHERE user_id=? ORDER BY updated DESC"), (user_id,))
        return _rows(cur)


def get_conversation(conv_id: int) -> dict[str, Any] | None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT * FROM conversations WHERE id=?"), (conv_id,))
        return _one(cur)


def rename_conversation(conv_id: int, title: str) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE conversations SET title=? WHERE id=?"),
                    (title[:80], conv_id))
        c.commit()


def touch_conversation(conv_id: int) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE conversations SET updated=? WHERE id=?"),
                    (time.time(), conv_id))
        c.commit()


def delete_conversation(conv_id: int) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM messages WHERE conversation_id=?"), (conv_id,))
        cur.execute(_q("DELETE FROM conversations WHERE id=?"), (conv_id,))
        c.commit()


# ------------------------------ messages ----------------------------

def add_message(conv_id: int, user_id: int, role: str, content: str) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(
            _q("INSERT INTO messages (conversation_id, user_id, role, content, ts) "
               "VALUES (?,?,?,?,?)"), (conv_id, user_id, role, content, time.time()))
        c.commit()
    touch_conversation(conv_id)


def get_messages(conv_id: int, limit: int = 100) -> list[dict[str, str]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT role, content FROM messages WHERE conversation_id=? "
                       "ORDER BY id DESC LIMIT ?"), (conv_id, limit))
        rows = _rows(cur)
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


def clear_conversation(conv_id: int) -> None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("DELETE FROM messages WHERE conversation_id=?"), (conv_id,))
        c.commit()


# ------------------------------- notes ------------------------------

def add_note(user_id: int, text: str, tag: str = "") -> int:
    return _insert_returning(
        "INSERT INTO notes (user_id, text, tag, ts) VALUES (?,?,?,?)",
        (user_id, text, tag, time.time()))


def list_notes(user_id: int) -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT id, text, tag, ts FROM notes WHERE user_id=? "
                       "ORDER BY id DESC"), (user_id,))
        return _rows(cur)


# ------------------------------- tasks ------------------------------

def add_task(user_id: int, title: str) -> int:
    return _insert_returning(
        "INSERT INTO tasks (user_id, title, done, ts) VALUES (?,?,0,?)",
        (user_id, title, time.time()))


def list_tasks(user_id: int) -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT id, title, done, ts FROM tasks WHERE user_id=? "
                       "ORDER BY done, id DESC"), (user_id,))
        return _rows(cur)


def complete_task(user_id: int, task_id: int) -> bool:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("UPDATE tasks SET done=1 WHERE id=? AND user_id=?"),
                    (task_id, user_id))
        c.commit()
        return cur.rowcount > 0


# ----------------------------- reminders ----------------------------

def add_reminder(user_id: int, text: str, due_epoch: float) -> int:
    return _insert_returning(
        "INSERT INTO reminders (user_id, text, due, fired, ts) VALUES (?,?,?,0,?)",
        (user_id, text, due_epoch, time.time()))


def list_reminders(user_id: int) -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT id, text, due, fired, ts FROM reminders "
                       "WHERE user_id=? ORDER BY due"), (user_id,))
        return _rows(cur)


# ------------------------------ profiles ----------------------------

def get_profile(user_id: int) -> dict[str, Any] | None:
    with _connect() as c:
        cur = c.cursor()
        cur.execute(_q("SELECT data FROM profiles WHERE user_id=?"), (user_id,))
        row = cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def save_profile(user_id: int, data: dict[str, Any]) -> None:
    payload = json.dumps(data)
    with _connect() as c:
        cur = c.cursor()
        if IS_PG:
            cur.execute(_q("INSERT INTO profiles (user_id, data) VALUES (?,?) "
                           "ON CONFLICT (user_id) DO UPDATE SET data=EXCLUDED.data"),
                        (user_id, payload))
        else:
            cur.execute(_q("INSERT OR REPLACE INTO profiles (user_id, data) "
                           "VALUES (?,?)"), (user_id, payload))
        c.commit()


# ------------------------------- stats ------------------------------

def global_stats() -> dict[str, Any]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        users = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM conversations")
        convs = int(cur.fetchone()[0])
        cur.execute("SELECT COUNT(*) FROM messages")
        msgs = int(cur.fetchone()[0])
    return {"users": users, "conversations": convs, "messages": msgs}


def user_stats() -> list[dict[str, Any]]:
    with _connect() as c:
        cur = c.cursor()
        cur.execute("""SELECT u.id, u.email,
            (SELECT COUNT(*) FROM conversations c WHERE c.user_id=u.id) AS conversations,
            (SELECT COUNT(*) FROM messages m WHERE m.user_id=u.id) AS messages
            FROM users u ORDER BY messages DESC""")
        return _rows(cur)
