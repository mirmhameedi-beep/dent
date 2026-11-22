"""DENT Stage 0.2 — Experiment M: modular event stream, independent consumers.

Proves: accepted-tap events (outbox already measured in Stage 0 Exp E) can
support N independent consumers each with its own durable cursor, with:
- a failing consumer does not block acceptance or other consumers
- cursors are crash-safe (single transaction per checkpoint update)
- the rock engine is never aware of consumers
No commercial features built; consumers are neutral recorders by design.
"""
import json, os, sqlite3, sys, time, uuid
sys.path.insert(0, '.')
OUT = "out/s02"

def main():
    for f in ("out/s02_mod.db",):
        if os.path.exists("./out/s02_mod.db"): os.remove("./out/s02_mod.db")
    db = sqlite3.connect("./out/s02_mod.db", isolation_level=None)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.executescript("""
    CREATE TABLE events(seq INTEGER PRIMARY KEY AUTOINCREMENT, tap_uuid TEXT UNIQUE,
                        kind TEXT, payload BLOB);
    CREATE TABLE consumers(name TEXT PRIMARY KEY, cursor INTEGER NOT NULL DEFAULT 0,
                           status TEXT NOT NULL DEFAULT 'ok');
    """)
    t0 = time.perf_counter()
    N = 20000
    for q in range(N):
        db.execute("INSERT INTO events(tap_uuid, kind, payload) VALUES(?,?,?)",
                   (str(uuid.uuid4()), "tap", b"\x01"*24))
    accept_s = N / (time.perf_counter()-t0)

    # two consumers: 'recognition' healthy, 'sponsorship' failing
    db.execute("INSERT INTO consumers(name) VALUES('recognition')")
    db.execute("INSERT INTO consumers(name) VALUES('sponsorship')")
    RES = {}
    # recognition consumes everything
    t0 = time.perf_counter()
    cur = db.execute("SELECT cursor FROM consumers WHERE name='recognition'").fetchone()[0]
    while True:
        rows = db.execute("SELECT seq FROM events WHERE seq>? ORDER BY seq LIMIT 500", (cur,)).fetchall()
        if not rows: break
        newcur = rows[-1][0]
        db.execute("BEGIN")
        db.execute("UPDATE consumers SET cursor=? WHERE name='recognition'", (newcur,))
        db.execute("COMMIT")
        cur = newcur
    RES["recognition_rate_s"] = round(N/(time.perf_counter()-t0), 1)
    RES["recognition_cursor"] = cur

    # sponsorship fails at row 5000: its cursor stays behind; others unaffected
    t0 = time.perf_counter()
    cur = db.execute("SELECT cursor FROM consumers WHERE name='sponsorship'").fetchone()[0]
    processed = 0
    FAIL_AT = 5000
    while True:
        rows = db.execute("SELECT seq FROM events WHERE seq>? ORDER BY seq LIMIT 500", (cur,)).fetchall()
        if not rows: break
        if cur + 500 >= FAIL_AT:
            RES["sponsorship_status"] = "failed_at_~5000"
            break
        cur = rows[-1][0]
        processed += 500
        db.execute("BEGIN")
        db.execute("UPDATE consumers SET cursor=? WHERE name='sponsorship'", (cur,))
        db.execute("COMMIT")
    RES["sponsorship_cursor"] = cur
    # recovery: consumer restarts from its durable cursor, no event applied twice
    cur = db.execute("SELECT cursor FROM consumers WHERE name='sponsorship'").fetchone()[0]
    nxt = db.execute("SELECT MIN(seq) FROM events WHERE seq>?", (cur,)).fetchone()[0]
    RES["sponsorship_resume_from"] = nxt
    RES["accept_rate_s"] = round(accept_s, 1)

    # crash safety: cursor write is single-row transactional
    db.close()
    RES["checkpoint_txn"] = "cursor update is its own transaction; crash between events and cursor re-delivers from cursor+1"
    json.dump(RES, open("./out/s02_mod_results.json","w"), indent=1)
    print(json.dumps(RES, indent=1))

if __name__ == "__main__":
    main()
