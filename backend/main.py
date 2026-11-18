from __future__ import annotations

import os
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

TARGET = 1_000_000_000
DB_PATH = os.environ.get("DENT_DB", "dent.db")


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Dent", lifespan=lifespan)


class Tap(BaseModel):
    mac: str = Field(min_length=8, max_length=64)
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


@app.get("/stone")
def stone() -> dict:
    with db() as conn:
        total = conn.execute("SELECT total FROM counters WHERE id = 1").fetchone()["total"]
    return {"total": total, "target": TARGET, "remaining": TARGET - total}


@app.post("/tap")
def tap(payload: Tap) -> dict:
    now = time.time()
    with db() as conn:
        conn.execute(
            "INSERT INTO tappers (mac, taps, first_seen, last_seen) VALUES (?, 1, ?, ?) "
            "ON CONFLICT(mac) DO UPDATE SET taps = taps + 1, last_seen = ?",
            (payload.mac, now, now, now),
        )
        total = conn.execute(
            "UPDATE counters SET total = total + 1 WHERE id = 1 RETURNING total"
        ).fetchone()["total"]
    return {"total": total, "at": now, "dent_id": str(uuid.uuid4())}


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
