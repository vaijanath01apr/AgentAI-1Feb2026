"""
SQLite-backed persistent session store.

Replaces the in-memory `conversation_store` dict in main.py so that
conversation state (messages, booking progress) survives server restarts
and supports proper multi-turn follow-up conversations.

Schema
──────
  sessions  — one row per conversation session (booking fields flattened)
  messages  — full message history for every session
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from models.state import (
    TravelAgentState, TravelBooking, CustomerInfo, ConversationMessage
)

DB_PATH = Path(__file__).parent.parent / "data" / "sessions.db"


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur  = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id          TEXT PRIMARY KEY,
            created_at          TEXT NOT NULL,
            updated_at          TEXT NOT NULL,
            is_complete         INTEGER NOT NULL DEFAULT 0,
            current_agent       TEXT,
            query_type          TEXT,

            -- booking fields (flattened for easy querying)
            booking_id          TEXT,
            booking_stage       TEXT DEFAULT 'collecting_info',
            booking_status      TEXT DEFAULT 'pending',

            origin              TEXT,
            destination         TEXT,
            departure_date      TEXT,
            return_date         TEXT,
            travelers           INTEGER DEFAULT 1,
            cabin_class         TEXT DEFAULT 'Economy',

            selected_flight_id  INTEGER,
            flight_number       TEXT,
            airline             TEXT,
            price               REAL,
            currency            TEXT,

            last_flights_json   TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            agent_name  TEXT,
            timestamp   TEXT    NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                ON DELETE CASCADE
        );
    """)

    conn.commit()

    # Migration: add last_flights_json if upgrading an older DB
    try:
        cur.execute("ALTER TABLE sessions ADD COLUMN last_flights_json TEXT DEFAULT '[]'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists

    conn.close()
    print(f"[SessionStore] SQLite DB ready at {DB_PATH}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_booking(row) -> TravelBooking:
    return TravelBooking(
        booking_id=row["booking_id"],
        origin=row["origin"],
        destination=row["destination"],
        departure_date=row["departure_date"],
        return_date=row["return_date"],
        travelers=row["travelers"] or 1,
        cabin_class=row["cabin_class"] or "Economy",
        booking_status=row["booking_status"] or "pending",
        booking_stage=row["booking_stage"] or "collecting_info",
        selected_flight_id=row["selected_flight_id"],
        flight_number=row["flight_number"],
        airline=row["airline"],
        price=row["price"],
        currency=row["currency"],
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_session(session_id: str) -> Optional[dict]:
    """
    Load a full session from SQLite.

    Returns a plain dict with keys:
        session_id, messages, booking_info, is_complete,
        current_agent, query_type, created_at, updated_at

    Returns None if the session doesn't exist yet.
    """
    conn = _get_conn()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return None

    cur.execute(
        "SELECT role, content, agent_name, timestamp "
        "FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,),
    )
    msg_rows = cur.fetchall()
    conn.close()

    messages = [
        ConversationMessage(
            role=m["role"],
            content=m["content"],
            agent_name=m["agent_name"],
            timestamp=datetime.fromisoformat(m["timestamp"]),
        )
        for m in msg_rows
    ]

    return {
        "session_id":       session_id,
        "messages":         messages,
        "booking_info":     _row_to_booking(row),
        "is_complete":      bool(row["is_complete"]),
        "current_agent":    row["current_agent"],
        "query_type":       row["query_type"],
        "created_at":       datetime.fromisoformat(row["created_at"]),
        "updated_at":       datetime.fromisoformat(row["updated_at"]),
        "last_flights_json": row["last_flights_json"] or "[]",
    }


def save_session(session_id: str, state: TravelAgentState, created_at: datetime = None) -> None:
    """
    Upsert the full session state into SQLite.

    Deletes and rewrites all messages for the session on each save
    (simple and correct for a demo; use append-only in production).
    """
    conn = _get_conn()
    cur  = conn.cursor()

    now     = datetime.now().isoformat()
    created = (created_at or datetime.now()).isoformat()
    booking = state["booking_info"]

    last_flights_json = state.get("agent_responses", {}).get("last_flights_json", "[]")

    cur.execute("""
        INSERT INTO sessions (
            session_id, created_at, updated_at, is_complete, current_agent, query_type,
            booking_id, booking_stage, booking_status,
            origin, destination, departure_date, return_date, travelers, cabin_class,
            selected_flight_id, flight_number, airline, price, currency,
            last_flights_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
            updated_at         = excluded.updated_at,
            is_complete        = excluded.is_complete,
            current_agent      = excluded.current_agent,
            query_type         = excluded.query_type,
            booking_id         = excluded.booking_id,
            booking_stage      = excluded.booking_stage,
            booking_status     = excluded.booking_status,
            origin             = excluded.origin,
            destination        = excluded.destination,
            departure_date     = excluded.departure_date,
            return_date        = excluded.return_date,
            travelers          = excluded.travelers,
            cabin_class        = excluded.cabin_class,
            selected_flight_id = excluded.selected_flight_id,
            flight_number      = excluded.flight_number,
            airline            = excluded.airline,
            price              = excluded.price,
            currency           = excluded.currency,
            last_flights_json  = excluded.last_flights_json
    """, (
        session_id, created, now,
        1 if state.get("is_complete") else 0,
        state.get("current_agent"),
        state.get("query_type"),
        booking.get("booking_id"),
        booking.get("booking_stage", "collecting_info"),
        booking.get("booking_status", "pending"),
        booking.get("origin"),
        booking.get("destination"),
        booking.get("departure_date"),
        booking.get("return_date"),
        booking.get("travelers", 1),
        booking.get("cabin_class", "Economy"),
        booking.get("selected_flight_id"),
        booking.get("flight_number"),
        booking.get("airline"),
        booking.get("price"),
        booking.get("currency"),
        last_flights_json,
    ))

    # Rewrite all messages (idempotent)
    cur.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    for msg in state.get("messages", []):
        ts = msg["timestamp"]
        if isinstance(ts, datetime):
            ts = ts.isoformat()
        cur.execute(
            "INSERT INTO messages (session_id, role, content, agent_name, timestamp) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, msg["role"], msg["content"], msg.get("agent_name"), ts),
        )

    conn.commit()
    conn.close()


def delete_session(session_id: str) -> bool:
    """Delete a session and all its messages. Returns True if found."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM messages  WHERE session_id = ?", (session_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def list_sessions() -> list:
    """Return summary rows for all sessions, newest first."""
    conn = _get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT
            s.session_id, s.created_at, s.updated_at,
            s.is_complete, s.current_agent,
            s.destination, s.booking_stage, s.booking_status,
            COUNT(m.id) AS message_count
        FROM sessions s
        LEFT JOIN messages m ON s.session_id = m.session_id
        GROUP BY s.session_id
        ORDER BY s.updated_at DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def cleanup_old_sessions(max_age_hours: int = 24, max_sessions: int = 500) -> int:
    """
    Remove sessions older than max_age_hours and keep at most max_sessions.
    Returns the number of sessions removed.
    """
    conn = _get_conn()
    cur  = conn.cursor()

    # Delete sessions older than threshold
    cur.execute(
        "DELETE FROM sessions WHERE updated_at < datetime('now', ? || ' hours')",
        (f"-{max_age_hours}",),
    )
    removed = cur.rowcount

    # Keep only the newest max_sessions
    cur.execute("""
        DELETE FROM sessions WHERE session_id NOT IN (
            SELECT session_id FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
        )
    """, (max_sessions,))
    removed += cur.rowcount

    conn.commit()
    conn.close()
    return removed
