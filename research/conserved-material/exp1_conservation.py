"""EXPERIMENT 1 - Material conservation under concentrated / clustered /
distributed 20k-tap histories at the billion calibration (alpha = 0.00197456,
same as Model A's calib2). Uses the reconstructed initial rock (147,908 cells).

Ledger snapshot at every milestone; O(V) full audit; identity must balance
exactly (integer).
"""
import json
import sys
import time

from common import gen_rock2
import modelA_stage03 as A
import cm_rock
import streams

ALPHA_BILLION = 0.00197456
MILESTONES = (1000, 5000, 10000, 20000)


def build():
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000,
                                 reserve_frac=0.02, mode="per_tap",
                                 debris_policy="hold")
    rock.alpha = ALPHA_BILLION
    return rock


def main():
    out = {"config": {"target": 20000, "alpha": ALPHA_BILLION,
                      "lattice": 72, "dfix": 65536}}
    for hist in ("A_concentrated", "C_clustered", "B_distributed"):
        rock = build()
        t0 = time.perf_counter()
        snaps = streams.run_stream(rock, streams.HistStream(rock, hist),
                                   20000, MILESTONES)
        final = rock.audit_ledger()
        out[hist] = dict(
            wall_s=snaps["wall_s"], accepted=snaps["accepted"],
            launched=snaps["launched"],
            build_s=round(0, 1),
            calib=rock.calib,
            snapshots={str(k): v for k, v in snaps.items()
                       if k in MILESTONES},
            violations_ledger=len(getattr(rock, "violations_ledger", [])),
            violations_allowance=len(getattr(rock, "violations_allowance", [])),
            violations_reserve=len(getattr(rock, "violations_reserve", [])),
            final=final,
            blocks_with_debris=len(rock.debris),
            ledger_overhead_s=round(0, 3))
        print(hist, "done", out[hist]["accepted"], "accepted,",
              "identity_ok" if final["balance_residual"] == 0 and
              final["tracker_drift"] == 0 else "IDENTITY VIOLATION",
              "consumed", final["consumed"] / rock.dfix,
              "debris", final["debris_total"] / rock.dfix,
              "frag_cells", final["fragment_cells"],
              flush=True)
    with open("results/e1_conservation.json", "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
