"""Database access for the Campus Customs MCP server.

The server only ever touches the WORKING copy, data/campus_customs_new.db.
The original data/campus_customs.db is never opened here, so it stays a clean reset point.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CAMPUS_DB", ROOT / "data" / "campus_customs_new.db"))

# Two working tables the original database doesn't have. They hold the human-approval
# queue and the customer message drafts. They are created on first use, so a reset
# (copying the original over the working copy) clears them too.
EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    kind TEXT NOT NULL CHECK (kind IN ('invoice', 'rent', 'purchase_order', 'discount')),
    ref_id INTEGER,
    payee TEXT NOT NULL,
    amount REAL NOT NULL,
    details TEXT,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'paid')),
    decided_by TEXT,
    decided_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_drafts (
    id INTEGER PRIMARY KEY,
    ticket_id INTEGER REFERENCES tickets(id),
    to_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    drafted_by TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TEXT NOT NULL
);
"""


@contextmanager
def connect():
    """Open the working database for one tool call: commit on success, roll back on error,
    and always CLOSE, so no file handle is left open (Windows needs this for a reset).
    Rows come back as dicts; foreign keys are enforced."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Working database not found at {DB_PATH}. "
            "Copy data/campus_customs.db to data/campus_customs_new.db first."
        )
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")  # declared in the schema but off by default
        conn.executescript(EXTRA_SCHEMA)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


def one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> dict | None:
    r = conn.execute(sql, params).fetchone()
    return dict(r) if r else None


def today(conn: sqlite3.Connection) -> str:
    """The shop's 'today' comes from desk.date_today, never from the computer clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    if row is None:
        raise ValueError("desk table has no date_today row")
    return row["date_today"]


def days_between(start: str, end: str) -> int:
    """Whole days from start to end (ISO dates). Negative if end is before start."""
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def add_days(day: str, n: int) -> str:
    from datetime import timedelta

    return (date.fromisoformat(day[:10]) + timedelta(days=n)).isoformat()


def add_month(day: str) -> str:
    d = date.fromisoformat(day[:10])
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    import calendar

    return date(y, m, min(d.day, calendar.monthrange(y, m)[1])).isoformat()
