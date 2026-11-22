"""PART D - Durable completion and crash recovery tests.

Actually runs worker subprocesses and kills them with os._exit(137) at 6
instrumented crash points, plus real SIGKILL from the parent, plus duplicate
replay / concurrent final-tap / post-completion / repeated terminal /
restart-after-terminal / death-between-completion-and-publication cases.

Every test records setup / expected / actual / evidence.
"""
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time

import store

BASE = "/tmp/dent-poc/model-a-prime"
DBDIR = os.path.join(BASE, "db")
PY = sys.executable


def run_worker(db, n_taps=1, prefix="w", crash=None, timeout=120):
    cmd = [PY, os.path.join(BASE, "src", "worker.py"), db,
           "--n-taps", str(n_taps), "--uuid-prefix", prefix]
    if crash:
        cmd += ["--crash-point", crash]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return p


def sigkill_during_mid_txn(db, delay):
    """Parent launches a worker that starts a tap transaction and we SIGKILL
    it mid-transaction."""
    p = subprocess.Popen(
        [PY, os.path.join(BASE, "src", "worker.py"), db,
         "--n-taps", "30", "--uuid-prefix", "k"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(delay)
    p.send_signal(signal.SIGKILL)
    p.wait()
    return p.returncode


def fresh_db(name, N=1000, pre_accept=0):
    db = os.path.join(DBDIR, name)
    store.init_db(db, N=N)
    if pre_accept:
        run_worker(db, n_taps=pre_accept, prefix="pre")
    return db


results = []


def record(name, setup, expect, actual, evidence, ok):
    results.append(dict(name=name, setup=setup, expected=expect,
                        actual=actual, evidence=evidence, ok=ok))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


def t_crash_points():
    # --- crash 1: before tap transaction begins ---
    db = fresh_db("d1_crash_before.db", N=10)
    p = run_worker(db, n_taps=1, prefix="c1", crash="before_txn")
    con = store.connect(db)
    st = store.check_consistency(con)
    r2 = run_worker(db, n_taps=10, prefix="c1")
    st2 = store.durable_state(con)
    record("crash_before_txn",
           "N=10; worker killed (exit 137) before any tap transaction",
           "no partial tap rows; restart accepts taps normally",
           dict(exit=p.returncode, consistency=st, after_restart=st2),
           "db/d1_crash_before.db", st["ok"] and st2["max_n"] == 10
           and st2["completed"])

    # --- crash 2: during tap transaction before commit ---
    db = fresh_db("d2_crash_precommit.db", N=10)
    p = run_worker(db, n_taps=1, prefix="c2", crash="in_txn_pre_commit")
    con = store.connect(db)
    st = store.check_consistency(con)
    r2 = run_worker(db, n_taps=10, prefix="c2")
    st2 = store.durable_state(con)
    record("crash_in_txn_pre_commit",
           "N=10; worker inserts a tap row, dies (exit 137) BEFORE commit",
           "insert rolled back; no partial row; restarted worker fills 1..10",
           dict(exit=p.returncode, consistency=st, after_restart=st2),
           "db/d2_crash_precommit.db",
           st["ok"] and st["state"]["rows"] == 0 and st2["max_n"] == 10)

    # --- crash 3: immediately after tap commit ---
    db = fresh_db("d3_crash_postcommit.db", N=10)
    p = run_worker(db, n_taps=5, prefix="c3", crash="after_commit")
    con = store.connect(db)
    st = store.check_consistency(con)
    r2 = run_worker(db, n_taps=10, prefix="c3")
    # duplicate uuid on committed row must be idempotent
    dup = store.claim_tap(con, "c3-k0")
    record("crash_after_commit",
           "N=10; worker dies right after its 5th COMMIT; then restart",
           "committed rows persist; restart continues to N; replaying a "
           "committed uuid returns the same n without a new row",
           dict(exit=p.returncode, consistency=st, after_restart=st2,
                duplicate_replay=dup),
           "db/d3_crash_postcommit.db",
           st["ok"] and st2["max_n"] == 10 and dup.get("duplicate")
           and dup.get("n") == 1)

    # --- crash 4: during terminal processing ---
    db = fresh_db("d4_crash_terminal.db", N=10)
    p = run_worker(db, n_taps=10, prefix="c4", crash="during_terminal")
    con = store.connect(db)
    st = store.durable_state(con)
    # post-completion tap must be rejected
    post = store.claim_tap(con, "post-completion-tap")
    post2 = store.claim_tap(con, "post-completion-tap")
    # recovery must create exactly one terminal event
    p2 = run_worker(db, n_taps=1, prefix="c4", crash="during_recovery")
    con2 = store.connect(db)
    p3 = run_worker(db, n_taps=1, prefix="c4")
    con3 = store.connect(db)
    st3 = store.durable_state(con3)
    ev = con3.execute("SELECT COUNT(*) FROM events WHERE kind='terminal'"
                      ).fetchone()[0]
    record("crash_during_terminal",
           "N=10; 10th tap commits completed=1, worker dies before terminal "
           "event row; then recovery worker also dies mid-recovery",
           "completed stays 1; post-completion tap rejected; recovery "
           "(rerun) creates exactly ONE terminal event; taps stay at 10",
           dict(exit=p.returncode, state_after=st, post_completion=post,
                post_completion_replay=post2,
                recovery_1_exit=p2.returncode, state_final=st3,
                terminal_event_rows=ev),
           "db/d4_crash_terminal.db",
           st["completed"] and not post["ok"] and st3["rows"] == 10
           and ev == 1 and st3["terminal_events"] == 1)

    # --- crash 5: after completion, before publication ---
    db = fresh_db("d5_crash_before_pub.db", N=10)
    p = run_worker(db, n_taps=10, prefix="c5", crash="before_publication")
    con = store.connect(db)
    st = store.durable_state(con)
    p2 = run_worker(db, n_taps=1, prefix="c5")     # recovery publishes
    con2 = store.connect(db)
    st2 = store.durable_state(con2)
    unp = con2.execute("SELECT payload, published FROM events "
                       "WHERE kind='terminal'").fetchall()
    record("crash_before_publication",
           "N=10; tap 10 commits, terminal event row written, worker dies "
           "before setting published flags",
           "recovery sets published=1 exactly once; event payload intact; "
           "no duplicate event",
           dict(exit=p.returncode, state_after=st, after_recovery=st2,
                terminal_event_rows=unp),
           "db/d5_crash_before_pub.db",
           st["unpublished"] == 1 and st2["unpublished"] == 0
           and len(unp) == 1)

    # --- crash 6: during recovery ---
    db = fresh_db("d6_crash_during_recovery.db", N=10)
    run_worker(db, n_taps=10, prefix="c6")
    con = store.connect(db)
    store.ensure_terminal_event(con)     # event exists but unpublished
    p = run_worker(db, n_taps=1, prefix="c6", crash="during_recovery")
    con = store.connect(db)
    mid = store.durable_state(con)
    p2 = run_worker(db, n_taps=1, prefix="c6")
    con2 = store.connect(db)
    st2 = store.durable_state(con2)
    record("crash_during_recovery",
           "N=10 completed, terminal event unpublished; recovery worker "
           "SIGKILLed via os._exit mid-recovery, then rerun",
           "intermediate crash leaves consistent state; rerun finishes "
           "publication; exactly one terminal event",
           dict(exit=p.returncode, mid_state=mid, final=st2),
           "db/d6_crash_during_recovery.db",
           mid["terminal_events"] == 1 and st2["unpublished"] == 0
           and st2["rows"] == 10)


def t_sigkill_equivalence():
    db = fresh_db("d7_sigkill_mid_txn.db", N=10)
    rc = sigkill_during_mid_txn(db, 0.12)
    con = store.connect(db)
    st = store.check_consistency(con)
    r2 = run_worker(db, n_taps=10, prefix="k")
    con2 = store.connect(db)
    st2 = store.durable_state(con2)
    record("real_sigkill_mid_transaction",
           "worker runs 30 tap attempts (N=10 reached), parent sends real "
           "SIGKILL at 120ms (inside some tap transaction)",
           "no partial commit; counter contiguous; completion correct",
           dict(sig=rc, consistency=st, final=st2),
           "db/d7_sigkill_mid_txn.db",
           st["ok"] and st2["max_n"] == 10 and st2["completed"])


def t_concurrent_final_tap():
    db = fresh_db("d8_concurrent_final.db", N=10, pre_accept=9)
    procs = [subprocess.Popen(
        [PY, os.path.join(BASE, "src", "worker.py"), db,
         "--n-taps", "1", "--uuid-prefix", f"race{i}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for i in range(4)]
    outs = [p.communicate() for p in procs]
    con = store.connect(db)
    st = store.check_consistency(con)
    winners = con.execute("SELECT uuid FROM taps WHERE n=10").fetchall()
    record("concurrent_final_tap_race",
           "N=10, 9/10 accepted; four processes race for tap 10 with "
           "distinct uuids (busy_timeout 30s)",
           "exactly one winner; n sequence contiguous; completed=1",
           dict(state=st, winner=winners,
                rc=[p.returncode for p in procs]),
           "db/d8_concurrent_final.db",
           st["ok"] and len(winners) == 1 and st["state"]["completed"])


def t_no_caller_bypass():
    db = fresh_db("d9_no_bypass.db", N=10, pre_accept=9)
    con = store.connect(db)
    import inspect
    sig = str(inspect.signature(store.claim_tap))
    # try to claim with an injected "n" kwarg -> TypeError (no such parameter)
    bypass = None
    try:
        store.claim_tap(con, "attacker-uuid", n=10)
    except TypeError as e:
        bypass = str(e)
    r = store.claim_tap(con, "attacker-uuid")
    con2 = store.connect(db)
    st = store.durable_state(con2)
    record("no_caller_supplied_counter",
           "get_tap API inspected; attacker calls claim_tap(n=10) at 9/10",
           "no caller-controllable counter parameter exists (TypeError); "
           "normal claim gets n=10; counter stays authoritative",
           dict(signature=sig, injected_attempt=bypass,
                normal_claim=r, state=st),
           "db/d9_no_bypass.db",
           bypass is not None and r["ok"] and r["n"] == 10)


def t_repeated_idempotency():
    db = fresh_db("d10_idempotent.db", N=10)
    con = store.connect(db)
    a = store.claim_tap(con, "same-uuid")
    b = store.claim_tap(con, "same-uuid")
    c = store.claim_tap(con, "same-uuid")
    con2 = store.connect(db)
    st = store.check_consistency(con2)
    ok = st["ok"] and st["state"]["rows"] == 1 and a["n"] == b["n"] == c["n"] \
        and a["duplicate"] is False and b["duplicate"] is True
    # restart after terminal + repeated terminal processing
    fresh = fresh_db("d11_terminal_restart.db", N=10)
    run_worker(fresh, n_taps=10, prefix="t")
    con3 = store.connect(fresh)
    e1 = store.ensure_terminal_event(con3)
    e2 = store.ensure_terminal_event(con3)
    rc = run_worker(fresh, n_taps=3, prefix="t")   # taps after completion
    con4 = store.connect(fresh)
    post = con4.execute("SELECT COUNT(*) FROM taps WHERE uuid LIKE 't-k%' "
                        "AND n > 10").fetchone()[0]
    st4 = store.durable_state(con4)
    r4 = store.claim_tap(con4, "fresh-after-terminal")
    record("terminal_idempotency_and_restart",
           "duplicate uuid thrice; completion at N=10; ensure_terminal_event "
           "twice; worker restarted and taps after completion",
           "one row; counter unchanged; one terminal event; taps after "
           "completion rejected; state unambiguous",
           dict(three_claims=(a, b, c), consistency=st,
                terminal=(e1, e2), state_after_restart=st4,
                claim_after_terminal=r4,
                rows_after_n_gt_10=post),
           "db/d10_idempotent.db + db/d11_terminal_restart.db",
           ok and st4["rows"] == 10 and st4["terminal_events"] == 1
           and not r4["ok"])


def main():
    t_crash_points()
    t_sigkill_equivalence()
    t_concurrent_final_tap()
    t_no_caller_bypass()
    t_repeated_idempotency()
    out = dict(meta=dict(purpose="PART D durable completion + crash recovery",
                         db_engine="sqlite3 WAL, synchronous=FULL, "
                                   "busy_timeout=30000",
                         time=time.strftime("%Y-%m-%d %H:%M:%S")),
               tests=results,
               passed=sum(1 for r in results if r["ok"]),
               failed=sum(1 for r in results if not r["ok"]))
    with open(os.path.join(BASE, "results", "d_durable.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("PASS", out["passed"], "FAIL", out["failed"], flush=True)


if __name__ == "__main__":
    main()
