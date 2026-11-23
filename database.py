"""
Thin SQLite data layer shared by the bot process and the dashboard process.
Plain sqlite3 (no ORM) to keep the project easy to read and modify.
"""
import sqlite3
import time
from contextlib import contextmanager

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    joined_at   INTEGER NOT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS tickets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open',   -- open | closed
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL,
    sender      TEXT NOT NULL,                  -- user | admin
    text        TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    delivered   INTEGER NOT NULL DEFAULT 1,      -- 0 = admin reply not yet sent by bot
    FOREIGN KEY (ticket_id) REFERENCES tickets(id)
);

CREATE TABLE IF NOT EXISTS broadcasts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    text          TEXT NOT NULL,
    scheduled_at  INTEGER,                       -- NULL = send immediately
    sent_at       INTEGER,
    status        TEXT NOT NULL DEFAULT 'pending', -- pending | sending | sent | failed
    sent_count    INTEGER NOT NULL DEFAULT 0,
    failed_count  INTEGER NOT NULL DEFAULT 0,
    created_at    INTEGER NOT NULL
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # lets bot + dashboard share the file safely
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


# ---------- subscribers ----------

def add_subscriber(user_id: int, username: str, first_name: str):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO subscribers (user_id, username, first_name, joined_at, is_active)
               VALUES (?, ?, ?, ?, 1)
               ON CONFLICT(user_id) DO UPDATE SET is_active=1, username=excluded.username""",
            (user_id, username, first_name, int(time.time())),
        )


def remove_subscriber(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE subscribers SET is_active=0 WHERE user_id=?", (user_id,))


def active_subscriber_ids():
    with get_conn() as conn:
        rows = conn.execute("SELECT user_id FROM subscribers WHERE is_active=1").fetchall()
        return [r["user_id"] for r in rows]


def subscriber_stats():
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) c FROM subscribers").fetchone()["c"]
        active = conn.execute("SELECT COUNT(*) c FROM subscribers WHERE is_active=1").fetchone()["c"]
        last_7d = conn.execute(
            "SELECT COUNT(*) c FROM subscribers WHERE joined_at > ?",
            (int(time.time()) - 7 * 86400,),
        ).fetchone()["c"]
        return {"total": total, "active": active, "new_last_7d": last_7d}


# ---------- support tickets ----------

def get_or_create_open_ticket(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM tickets WHERE user_id=? AND status='open' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            return row["id"]
        now = int(time.time())
        cur = conn.execute(
            "INSERT INTO tickets (user_id, status, created_at, updated_at) VALUES (?, 'open', ?, ?)",
            (user_id, now, now),
        )
        return cur.lastrowid


def add_ticket_message(ticket_id: int, sender: str, text: str, delivered: bool = True):
    with get_conn() as conn:
        now = int(time.time())
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, created_at, delivered) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, sender, text, now, 1 if delivered else 0),
        )
        conn.execute("UPDATE tickets SET updated_at=? WHERE id=?", (now, ticket_id))


def list_tickets(status: str = "open"):
    with get_conn() as conn:
        return conn.execute(
            """SELECT t.*, s.username, s.first_name
               FROM tickets t LEFT JOIN subscribers s ON s.user_id = t.user_id
               WHERE t.status=? ORDER BY t.updated_at DESC""",
            (status,),
        ).fetchall()


def get_ticket(ticket_id: int):
    with get_conn() as conn:
        ticket = conn.execute(
            """SELECT t.*, s.username, s.first_name
               FROM tickets t LEFT JOIN subscribers s ON s.user_id = t.user_id
               WHERE t.id=?""",
            (ticket_id,),
        ).fetchone()
        messages = conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC", (ticket_id,)
        ).fetchall()
        return ticket, messages


def close_ticket(ticket_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE tickets SET status='closed', updated_at=? WHERE id=?", (int(time.time()), ticket_id))


def pending_admin_replies():
    """Admin replies typed in the dashboard that the bot process hasn't sent yet."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT tm.id as message_id, tm.text, t.user_id
               FROM ticket_messages tm JOIN tickets t ON t.id = tm.ticket_id
               WHERE tm.sender='admin' AND tm.delivered=0
               ORDER BY tm.id ASC"""
        ).fetchall()


def mark_delivered(message_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE ticket_messages SET delivered=1 WHERE id=?", (message_id,))


# ---------- broadcasts ----------

def create_broadcast(text: str, scheduled_at: int | None):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO broadcasts (text, scheduled_at, status, created_at) VALUES (?, ?, 'pending', ?)",
            (text, scheduled_at, int(time.time())),
        )
        return cur.lastrowid


def due_broadcasts():
    now = int(time.time())
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM broadcasts
               WHERE status='pending' AND (scheduled_at IS NULL OR scheduled_at <= ?)""",
            (now,),
        ).fetchall()


def mark_broadcast_sending(broadcast_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE broadcasts SET status='sending' WHERE id=?", (broadcast_id,))


def finish_broadcast(broadcast_id: int, sent_count: int, failed_count: int):
    with get_conn() as conn:
        conn.execute(
            """UPDATE broadcasts SET status='sent', sent_at=?, sent_count=?, failed_count=?
               WHERE id=?""",
            (int(time.time()), sent_count, failed_count, broadcast_id),
        )


def list_broadcasts():
    with get_conn() as conn:
        return conn.execute("SELECT * FROM broadcasts ORDER BY id DESC LIMIT 50").fetchall()
