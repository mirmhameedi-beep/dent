"""EXPERIMENTS 3+4 combined - full-lifetime compressed runs (N*=20,000,
same scale as the Stage 0.3 7/7 completion suite).

For every history (concentrated, distributed, clustered, edge, adaptive
+ HOSTILE bore-pivot) the invariant

    physical(n) = density + debris + fines  >=  M0 - n*q   and  >  Mr  (n < N)

is checked after EVERY accepted tap, and the ledger identity

    density + debris + fines + consumed == M0

is O(V) audited at milestones. Spatial differentiation (E4) is recorded from
the terminal pre-states: cells removed, density loss, debris, fragments.

Also runs one 'cumulative' allowance-mode case on the concentrated stream to
measure how much a single tap may consume when the whole lifetime allowance is
available (the "unused allowance pile-up" question).
"""
import json
import time

from common import gen_rock2
import cm_rock
import streams

MILESTONES = (1000, 5000, 10000, 20000)
N = 20000


def build(hist_mode="per_tap", policy="hold", n=N, alpha=None):
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=n,
                                 mode=hist_mode, debris_policy=policy)
    # compressed calibration, mirroring s03_complete.build_rock:
    dsum = sum(rock.density.values()) / rock.dfix
    cap = rock.q_legacy          # conserved: derived from q=(M0-Mr)//N
    rock.alpha = alpha if alpha is not None else cap / 15.33
    return rock


def run(hist, mode="per_tap", policy="hold", n=N):
    rock = build(mode, policy, n)
    if hist == "HOSTILE":
        stream = streams.HostileStream(rock)
    else:
        stream = streams.HistStream(rock, hist)
    t0 = time.perf_counter()
    snaps = streams.run_stream(rock, stream, n, MILESTONES)
    wall = time.perf_counter() - t0
    pre = rock.audit_ledger()
    grew = dict(
        wall_s=round(wall, 1), accepted=snaps["accepted"],
        launched=snaps["launched"],
        calib=rock.calib,
        milestones={str(k): {kk: (vv / rock.dfix if kk in (
            "density_sum", "debris_total", "consumed") else vv)
            for kk, vv in v.items() if kk in (
            "density_sum", "debris_total", "consumed",
            "balance_residual", "tracker_drift", "fragment_cells",
            "fragment_components")}
            for k, v in snaps.items() if k in MILESTONES},
        violations_ledger=len(getattr(rock, "violations_ledger", [])),
        violations_allowance=len(getattr(rock, "violations_allowance", [])),
        violations_reserve=len(getattr(rock, "violations_reserve", [])),
        q_tap_legacy=rock.q_legacy,
        pre_terminal_audit={k: (v / rock.dfix if k in (
            "density_sum", "debris_total", "consumed") else v)
            for k, v in pre.items()},
    )
    return rock, grew


def main():
    out = {"config": {"N": N, "milestones": MILESTONES,
                      "note": "invariant checked after every accepted tap"}}
    for hist in ("A_concentrated", "A_rot", "B_distributed", "C_clustered",
                 "D_edge", "E_adaptive", "HOSTILE"):
        rock, rec = run(hist)
        out[hist] = rec
        print(hist, "done:", rec["accepted"], "accepted,",
              "ledger_ok" if rec["violations_ledger"] == 0 and
              rec["violations_reserve"] == 0 and rec["violations_allowance"] == 0
              else "VIOLATIONS",
              "| physical_before(Mr frac):",
              round(rec["pre_terminal_audit"]["density_sum"] /
                    (rock.M0 / rock.dfix), 4),
              flush=True)
    # one cumulative-mode case
    rock, rec = run("A_concentrated", mode="cumulative")
    out["A_concentrated_cumulative"] = rec
    print("cumulative-mode done:", rec["accepted"], flush=True)
    with open("results/e3_e4_invariant.json", "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
