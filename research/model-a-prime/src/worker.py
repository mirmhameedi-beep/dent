"""PART D worker: accepts taps against the durable store, can be killed at
instrumented crash points (os._exit stays *unclean* like SIGKILL for sqlite
commit guarantees; the parent additionally sends a real SIGKILL for one
equivalence test).

Usage:
  python3 worker.py <db> --n-taps M --uuid-prefix P --crash-point CP

crash points:
  before_txn            kill before the tap transaction begins
  in_txn_pre_commit     kill inside the transaction, before COMMIT
  after_commit          kill immediately after COMMIT
  during_terminal       kill between durable completion and the terminal
                        event row being written
  before_publication    kill after terminal event row exists, before
                        publication flags are set
  during_recovery       recovery pass is started then killed mid-way
"""
import argparse
import os
import sys

import store


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--n-taps", type=int, default=1)
    ap.add_argument("--uuid-prefix", default="w")
    ap.add_argument("--crash-point", default=None)
    args = ap.parse_args()

    con = store.connect(args.db)
    rec_actions = store.recover(con)   # boot-time recovery: idempotent drain
    if rec_actions:
        sys.stderr.write(f"recovery actions on boot: {rec_actions}\n")
    done = 0
    launched = 0
    last = None
    for k in range(args.n_taps):
        launched += 1
        if args.crash_point == "before_txn":
            os._exit(137)
        if args.crash_point == "in_txn_pre_commit":
            con.execute("BEGIN IMMEDIATE")
            n = con.execute("SELECT COUNT(*) FROM taps").fetchone()[0] + 1
            con.execute("INSERT INTO taps(uuid, n, verdict, state_hash, ts) "
                        "VALUES(?,?,?,?,?)",
                        (f"{args.uuid_prefix}-k{k}", n, "accepted", "h",
                         0.0))
            os._exit(137)          # die BEFORE COMMIT: must roll back
        r = store.claim_tap(con, f"{args.uuid_prefix}-k{k}")
        last = r
        if args.crash_point == "after_commit":
            os._exit(137)
        if r.get("ok"):
            done += 1
        if args.crash_point == "during_terminal" and r.get("completed"):
            os._exit(137)          # completed=1 durable; event row NOT created
        if args.crash_point == "before_publication" and r.get("completed"):
            store.ensure_terminal_event(con)
            os._exit(137)          # event row exists; published flags unset
    if args.crash_point == "during_recovery":
        acts = store.recover(con)   # partial recovery pass
        os._exit(137)
    sys.stderr.write(f"worker done: accepted={done} launched={launched} "
                     f"last={last}\n")
    print("accepted=", done, "last=", last)


if __name__ == "__main__":
    main()
