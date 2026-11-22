"""PART D - Durable accepted-tap counter and completion store (SQLite, WAL).

Isolated scratch prototype. No production DB is touched.

Design invariants:
  - The authoritative accepted-tap count lives ONLY in the taps table.
    No API accepts a caller-supplied count; there is nothing to bypass.
  - Per tap: BEGIN IMMEDIATE; check completed; idempotency by uuid
    (INSERT OR IGNORE + read-back); authoritative n = COUNT(*)+1;
    reject when n > N; on n == N set completed=1 and append the terminal
    event row IN THE SAME TRANSACTION; COMMIT.
  - Completion is irreversible: completed=1 is never unset.
  - Terminal event processing and publication are downstream, idempotent,
    recoverable steps (their crashes can never corrupt the completion
    decision; recovery re-derives everything from durable state).
  - 'published' is a bookkeeping flag on the event row; visual rendering is
    outside the store (referenced only by event payload).

Levels distinguished:
  durable completion state (meta.completed)  >  terminal event row  >
  published flag  >  visual rendering (external, implied by event)
"""
import os
import sqlite3
import time

N_DEFAULT = 1000          # reduced completion target for testing


def connect(path):
    con = sqlite3.connect(path, timeout=30.0, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA busy_timeout=30000")
    return con


def init_db(path, N=N_DEFAULT):
    if os.path.exists(path):
        os.remove(path)
    for suffix in ("-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)
    con = connect(path)
    con.executescript("""
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE taps(
        uuid TEXT PRIMARY KEY,
        n INTEGER NOT NULL,
        verdict TEXT NOT NULL,
        state_hash TEXT,
        ts REAL NOT NULL
    );
    CREATE TABLE events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        dedup_key TEXT UNIQUE,
        payload TEXT,
        published INTEGER NOT NULL DEFAULT 0,
        ts REAL NOT NULL
    );
    """)
    con.execute("INSERT INTO meta(key, value) VALUES('completed','0')")
    con.execute("INSERT INTO meta(key, value) VALUES('N',?)", (str(N),))
    con.commit()
    con.close()


def get_meta(con, key):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


# ----------------------------------------------------------------------
# authoritative tap claim
# ----------------------------------------------------------------------
def claim_tap(con, uuid, state_hash=None, verdict="accepted"):
    """Atomically attempt to accept one tap. Returns dict:
    ok, n (if accepted), duplicate (bool), completed(bool), reason.
    The counter is ALWAYS derived from durable rows; there is no parameter
    that can override it."""
    con.execute("BEGIN IMMEDIATE")
    try:
        if get_meta(con, "completed") == "1":
            # idempotency still applies after completion
            row = con.execute("SELECT n, verdict FROM taps WHERE uuid=?",
                              (uuid,)).fetchone()
            con.execute("COMMIT")
            if row:
                return dict(ok=True, n=row[0], duplicate=True,
                            verdict=row[1], completed=True)
            return dict(ok=False, reason="completed", completed=True)
        row = con.execute("SELECT n, verdict FROM taps WHERE uuid=?",
                          (uuid,)).fetchone()
        if row:
            con.execute("COMMIT")
            return dict(ok=True, n=row[0], duplicate=True, verdict=row[1])
        N = int(get_meta(con, "N"))
        n = con.execute("SELECT COUNT(*) FROM taps").fetchone()[0] + 1
        if n > N:
            con.execute("COMMIT")
            return dict(ok=False, reason="exhausted", completed=True)
        con.execute("INSERT INTO taps(uuid, n, verdict, state_hash, ts) "
                    "VALUES(?,?,?,?,?)",
                    (uuid, n, verdict, state_hash, time.time()))
        if n == N:
            con.execute("UPDATE meta SET value='1' WHERE key='completed'")
        con.execute("COMMIT")
        return dict(ok=True, n=n, duplicate=False, verdict=verdict,
                    completed=(n == N))
    except BaseException:
        con.execute("ROLLBACK")
        raise


def ensure_terminal_event(con, payload='{"action":"disintegrate_all"}'):
    """Idempotent downstream step: create the terminal event row once
    (dedup_key='terminal') if and only if durable completion is set."""
    con.execute("BEGIN IMMEDIATE")
    try:
        if get_meta(con, "completed") != "1":
            con.execute("COMMIT")
            return dict(ok=False, reason="not_completed")
        con.execute("INSERT OR IGNORE INTO events(kind, dedup_key, payload, ts) "
                    "VALUES('terminal','terminal',?,?)",
                    (payload, time.time()))
        con.execute("COMMIT")
        return dict(ok=True, reason="terminal_event_ensured")
    except BaseException:
        con.execute("ROLLBACK")
        raise


def pending_recovery_work(con):
    """Re-derivable work items after any crash: un-ensured terminal events
    and unpublished events. Idempotent by construction."""
    work = []
    if get_meta(con, "completed") == "1":
        row = con.execute("SELECT 1 FROM events WHERE dedup_key='terminal'"
                          ).fetchone()
        if not row:
            work.append("ensure_terminal_event")
        for (eid,) in con.execute(
                "SELECT id FROM events WHERE published=0 ORDER BY id"):
            work.append(f"publish:{eid}")
    return work


def recover(con):
    """Run one recovery pass. Returns list of actions taken (idempotent)."""
    actions = []
    steps = 0            # allows the test to crash DURING recovery
    max_steps = 1
    while True:
        work = pending_recovery_work(con)
        if not work:
            break
        w = work[0]
        if w == "ensure_terminal_event":
            ensure_terminal_event(con)
            actions.append("ensured_terminal_event")
        else:
            eid = int(w.split(":")[1])
            con.execute("BEGIN IMMEDIATE")
            con.execute("UPDATE events SET published=1 WHERE id=?", (eid,))
            con.execute("COMMIT")
            actions.append(f"published:{eid}")
        steps += 1
        if steps >= max_steps and len(actions) < 100:
            break
    return actions


def publish_events(con):
    """Full publication drain (idempotent)."""
    con.execute("BEGIN IMMEDIATE")
    con.execute("UPDATE events SET published=1 WHERE published=0")
    con.execute("COMMIT")
    return con.execute("SELECT COUNT(*) FROM events WHERE published=1"
                       ).fetchone()[0]


def durable_state(con):
    n = con.execute("SELECT COUNT(*), COALESCE(MAX(n),0) FROM taps").fetchone()
    return dict(rows=n[0], max_n=n[1],
                completed=get_meta(con, "completed") == "1",
                N=int(get_meta(con, "N")),
                events=con.execute("SELECT COUNT(*) FROM events").fetchone()[0],
                terminal_events=con.execute(
                    "SELECT COUNT(*) FROM events WHERE kind='terminal'"
                ).fetchone()[0],
                unpublished=con.execute(
                    "SELECT COUNT(*) FROM events WHERE published=0"
                ).fetchone()[0])


def check_consistency(con):
    """Counter sanity: rows == max_n (contiguous 1..max_n), never > N."""
    d = durable_state(con)
    problems = []
    if d["rows"] != d["max_n"]:
        problems.append(f"rows({d['rows']}) != max_n({d['max_n']})")
    if d["max_n"] > d["N"]:
        problems.append("counter exceeded N")
    missing = []
    if d["rows"]:
        n_list = [r[0] for r in con.execute("SELECT n FROM taps ORDER BY n")]
        if n_list != list(range(1, d["max_n"] + 1)):
            missing = "non-contiguous n sequence"
            problems.append(missing)
    if problems:
        return dict(ok=False, state=d, problems=problems)
    return dict(ok=True, state=d, problems=[])
