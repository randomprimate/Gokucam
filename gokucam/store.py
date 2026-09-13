"""
SQLite-backed datastore for biomarker history: snapshots, feeding log,
calibration, and measurements. One writer household, one file — sqlite3
from the stdlib is plenty; no ORM, just plain functions.
"""
import sqlite3
import threading
import time
from pathlib import Path
from typing import Optional

from .config import DB_PATH

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    captured_at REAL NOT NULL,
    reason TEXT NOT NULL CHECK (reason IN ('scheduled', 'manual'))
);

CREATE TABLE IF NOT EXISTS feeding_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    food TEXT NOT NULL,
    portion TEXT,
    note TEXT,
    logged_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS calibration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    px_per_cm REAL NOT NULL,
    established_at REAL NOT NULL,
    snapshot_id INTEGER REFERENCES snapshots(id)
);

CREATE TABLE IF NOT EXISTS measurements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id),
    calibration_id INTEGER NOT NULL REFERENCES calibration(id),
    px_distance REAL NOT NULL,
    cm_distance REAL NOT NULL,
    measured_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS health_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id),
    summary TEXT NOT NULL,
    concerning INTEGER NOT NULL DEFAULT 0,
    raw_response TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS post_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER REFERENCES snapshots(id),
    cadence TEXT NOT NULL CHECK (cadence IN ('roundup', 'highlight')),
    caption TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'approved', 'rejected')),
    created_at REAL NOT NULL,
    reviewed_at REAL
);

CREATE TABLE IF NOT EXISTS ai_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purpose TEXT NOT NULL,
    called_at REAL NOT NULL,
    ok INTEGER NOT NULL
);
"""


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        with _lock:
            _conn.executescript(_SCHEMA)
            _conn.commit()
    return _conn


def record_snapshot(path: str, reason: str, captured_at: Optional[float] = None) -> int:
    assert reason in ("scheduled", "manual")
    ts = captured_at if captured_at is not None else time.time()
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO snapshots (path, captured_at, reason) VALUES (?, ?, ?)",
            (path, ts, reason),
        )
        conn.commit()
        return cur.lastrowid


def log_feeding(food: str, portion: str = "", note: str = "", logged_at: Optional[float] = None) -> int:
    if not food or not food.strip():
        raise ValueError("food description is required")
    ts = logged_at if logged_at is not None else time.time()
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO feeding_log (food, portion, note, logged_at) VALUES (?, ?, ?, ?)",
            (food.strip(), portion, note, ts),
        )
        conn.commit()
        return cur.lastrowid


def set_calibration(px_per_cm: float, snapshot_id: Optional[int] = None) -> int:
    if px_per_cm <= 0:
        raise ValueError("px_per_cm must be positive")
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO calibration (px_per_cm, established_at, snapshot_id) VALUES (?, ?, ?)",
            (px_per_cm, time.time(), snapshot_id),
        )
        conn.commit()
        return cur.lastrowid


def get_snapshot(snapshot_id: int) -> Optional[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()


def get_latest_calibration() -> Optional[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM calibration ORDER BY established_at DESC LIMIT 1"
        ).fetchone()


def record_measurement(snapshot_id: Optional[int], calibration_id: int, px_distance: float, cm_distance: float) -> int:
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO measurements (snapshot_id, calibration_id, px_distance, cm_distance, measured_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, calibration_id, px_distance, cm_distance, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def recent_history(limit: int = 50) -> list[dict]:
    """Merged snapshots + feeding log + measurements, newest first."""
    conn = _get_conn()
    with _lock:
        snaps = conn.execute(
            "SELECT id, path, captured_at AS ts, reason FROM snapshots ORDER BY captured_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        feeds = conn.execute(
            "SELECT id, food, portion, note, logged_at AS ts FROM feeding_log ORDER BY logged_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        measures = conn.execute(
            "SELECT id, snapshot_id, cm_distance, measured_at AS ts FROM measurements ORDER BY measured_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

    events = []
    for r in snaps:
        events.append({"kind": "snapshot", "id": r["id"], "ts": r["ts"], "path": r["path"], "reason": r["reason"]})
    for r in feeds:
        events.append({"kind": "feeding", "id": r["id"], "ts": r["ts"], "food": r["food"], "portion": r["portion"], "note": r["note"]})
    for r in measures:
        events.append({"kind": "measurement", "id": r["id"], "ts": r["ts"], "snapshot_id": r["snapshot_id"], "cm_distance": r["cm_distance"]})

    events.sort(key=lambda e: e["ts"], reverse=True)
    return events[:limit]


def latest_snapshot() -> Optional[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute("SELECT * FROM snapshots ORDER BY captured_at DESC LIMIT 1").fetchone()


def recent_feeding(limit: int = 10) -> list[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM feeding_log ORDER BY logged_at DESC LIMIT ?", (limit,)
        ).fetchall()


def recent_measurements(limit: int = 10) -> list[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM measurements ORDER BY measured_at DESC LIMIT ?", (limit,)
        ).fetchall()


# --- AI insights: health notes ---
def record_health_note(snapshot_id: Optional[int], summary: str, concerning: bool, raw_response: str = "") -> int:
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO health_notes (snapshot_id, summary, concerning, raw_response, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (snapshot_id, summary, int(concerning), raw_response, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def recent_health_notes(limit: int = 20) -> list[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM health_notes ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()


# --- AI insights: post drafts ---
def create_draft(snapshot_id: Optional[int], cadence: str, caption: str) -> int:
    assert cadence in ("roundup", "highlight")
    conn = _get_conn()
    with _lock:
        cur = conn.execute(
            "INSERT INTO post_drafts (snapshot_id, cadence, caption, status, created_at) "
            "VALUES (?, ?, ?, 'pending_review', ?)",
            (snapshot_id, cadence, caption, time.time()),
        )
        conn.commit()
        return cur.lastrowid


def set_draft_status(draft_id: int, status: str) -> None:
    assert status in ("approved", "rejected")
    conn = _get_conn()
    with _lock:
        conn.execute(
            "UPDATE post_drafts SET status = ?, reviewed_at = ? WHERE id = ?",
            (status, time.time(), draft_id),
        )
        conn.commit()


def pending_drafts(limit: int = 20) -> list[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM post_drafts WHERE status = 'pending_review' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


def approved_drafts(limit: int = 20) -> list[sqlite3.Row]:
    conn = _get_conn()
    with _lock:
        return conn.execute(
            "SELECT * FROM post_drafts WHERE status = 'approved' ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()


# --- AI insights: daily call cap ---
def log_ai_call(purpose: str, ok: bool) -> None:
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO ai_call_log (purpose, called_at, ok) VALUES (?, ?, ?)",
            (purpose, time.time(), int(ok)),
        )
        conn.commit()


def calls_today() -> int:
    conn = _get_conn()
    midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    with _lock:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM ai_call_log WHERE called_at >= ?", (midnight,)
        ).fetchone()
        return row["n"]
