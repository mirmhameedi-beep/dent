"""EXPERIMENT 7 - Terminal event at exactly N (compressed demo N=5000).

NOT a billion-tap physical simulation: a compressed-lifetime run whose counter
reaches exactly N, at which point the terminal event is authorised once.

Checks: refusal at N-1; commit exactly at the accepting Nth tap; density,
debris, fines, bonds all cleared; burned + consumed == M0 (integer identity);
idempotent replay returns the same manifest; post-terminal taps rejected.
"""
import hashlib
import json
import random
import time

import cm_rock
import streams
from common import gen_rock2

N = 5000


def main():
    out = {"config": {"N": N, "note": "compressed terminal demo; not a 1e9 physical run"}}
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=N,
                                 debris_policy="shed")
    rock.alpha = rock.q_legacy / 15.33
    # drive to exactly N-1 accepted
    snaps = streams.run_stream(rock, streams.HistStream(rock, "B_distributed"),
                               N - 1, ())
    # negative control: terminal must refuse before N
    out["refusal_at_N_minus_1"] = rock.terminal_event(accepted_n=N - 1)
    # final tap(s): jittered re-aim until one is accepted (production rule)
    rnd = random.Random(31337)
    attempts = 0
    pre_m = None
    while rock.s["taps"] < N and attempts < 60:
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        vd = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))
        orig, d = streams.ray_into(rock, tgt, vd)
        pre_m = None
        r = rock.tap_ledger(orig, d)
        attempts += 1
        if r.get("ok") and rock.s["taps"] == N:
            pre_m = rock.audit_ledger()
            m = rock.terminal_event(accepted_n=N)
            break
    out["final_tap_attempts"] = attempts
    out["manifest"] = m
    # invariants at terminal
    out["identity_after_terminal"] = dict(
        burned=rock.burned, consumed=rock.consumed,
        burned_plus_consumed_eq_M0=rock.burned + rock.consumed == rock.M0,
        density_empty=not rock.density, debris_empty=not rock.debris,
        fines_empty=not rock.fines, severed_empty=not rock.severed,
        post_hash=rock.hash_state())
    replay = rock.terminal_event(accepted_n=N)
    out["idempotent_replay"] = dict(
        same_manifest=replay.get("manifest") == m,
        burned_unchanged=rock.burned == m["burned"])
    # post-terminal tap rejected
    tgt, vd = (0.3, 0.3, 0.0), (0.1, 0.1, 1.0)
    orig, d = streams.ray_into(rock, tgt, vd)
    out["post_terminal_tap"] = rock.tap_ledger(orig, d)
    # reserve during the whole run
    out["reserve_ok_all_taps"] = len(getattr(rock, "violations_reserve", [])) == 0
    out["ledger_ok_all_taps"] = len(getattr(rock, "violations_ledger", [])) == 0
    with open("results/e7_terminal.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str)[:2000])


if __name__ == "__main__":
    main()
