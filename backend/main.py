from __future__ import annotations

import os
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

TARGET = 1_000_000_000
DB_PATH = os.environ.get("DENT_DB", "dent.db")
MAC_TAPS_PER_SECOND = int(os.environ.get("DENT_MAC_TAPS_PER_SECOND", "12"))
IP_TAPS_PER_SECOND = int(os.environ.get("DENT_IP_TAPS_PER_SECOND", "120"))
RECENT_DENTS = 400

_rate_lock = threading.Lock()
_rate: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str, limit: int) -> bool:
    now = time.time()
    with _rate_lock:
        window = _rate[key]
        while window and now - window[0] > 1.0:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with db() as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS counters (id INTEGER PRIMARY KEY CHECK (id = 1), total INTEGER NOT NULL)"
        )
        conn.execute("INSERT OR IGNORE INTO counters (id, total) VALUES (1, 0)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tappers ("
            " mac TEXT PRIMARY KEY,"
            " taps INTEGER NOT NULL DEFAULT 0,"
            " first_seen REAL NOT NULL,"
            " last_seen REAL NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS dents ("
            " id TEXT PRIMARY KEY,"
            " x REAL NOT NULL,"
            " y REAL NOT NULL,"
            " mac TEXT NOT NULL,"
            " at REAL NOT NULL)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_dents_at ON dents (at DESC)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Dent", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)


class Tap(BaseModel):
    mac: str = Field(min_length=8, max_length=64)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


@app.get("/stone")
def stone(limit: int = RECENT_DENTS) -> dict:
    with db() as conn:
        total = conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"]
        rows = conn.execute(
            "SELECT id, x, y, mac, at FROM dents ORDER BY at DESC LIMIT ?",
            (max(0, min(limit, 2000)),),
        ).fetchall()
    return {
        "total": total,
        "target": TARGET,
        "remaining": TARGET - total,
        "dents": [
            {"id": row["id"], "x": row["x"], "y": row["y"], "mac": row["mac"], "at": row["at"]}
            for row in rows
        ],
    }


@app.post("/tap")
def tap(payload: Tap, request: Request) -> dict:
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    if not allow(f"ip:{ip}", IP_TAPS_PER_SECOND) or not allow(f"mac:{payload.mac}", MAC_TAPS_PER_SECOND):
        raise HTTPException(status_code=429, detail="Slow down. The stone is patient.")
    dent_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO dents (id, x, y, mac, at) VALUES (?, ?, ?, ?, ?)",
            (dent_id, payload.x, payload.y, payload.mac, now),
        )
        conn.execute(
            "INSERT INTO tappers (mac, taps, first_seen, last_seen) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(mac) DO UPDATE SET taps = taps + 1, last_seen = ?",
            (payload.mac, now, now, now),
        )
        total = conn.execute(
            "UPDATE counters SET total = total + 1 WHERE id = 1 RETURNING total"
        ).fetchone()["total"]
    return {
        "total": total,
        "at": now,
        "dent": {"id": dent_id, "x": payload.x, "y": payload.y, "mac": payload.mac, "at": now},
    }


@app.get("/wall")
def wall(limit: int = 50) -> list[dict]:
    """Top tappers, most dents first."""
    with db() as conn:
        rows = conn.execute(
            "SELECT mac, taps, last_seen FROM tappers ORDER BY taps DESC, last_seen ASC LIMIT ?",
            (min(limit, 500),),
        ).fetchall()
    return [
        {"mac": row["mac"], "taps": row["taps"], "at": row["last_seen"]}
        for row in rows
    ]


app.mount("/", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static"), html=True), name="web")
