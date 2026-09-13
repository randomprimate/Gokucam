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
