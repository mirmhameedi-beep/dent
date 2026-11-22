"""EXPERIMENT 2 - Threshold handling.

Drives the compressed-calibration rock through its full lifetime (N*=20,000,
uniform distributed stream): thousands of cells cross DENS_FAIL and crumble.
For every crumbled cell the residual must be routed (consumed or debris) and
the O(V) ledger audit must balance exactly. Both debris policies ('hold',
'shed') are exercised to prove the shed path also preserves the identity.
"""
import json
import time

from common import gen_rock2
import cm_rock
import streams


def run(policy):
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000,
                                 debris_policy=policy)
    rock.alpha = rock.q_legacy / 15.33
    t0 = time.perf_counter()
    snaps = streams.run_stream(rock, streams.HistStream(rock, "B_distributed"),
                               20000, (5000, 10000, 20000))
    audit = rock.audit_ledger()
    return dict(policy=policy, wall_s=round(time.perf_counter() - t0, 1),
                accepted=snaps["accepted"], launched=snaps["launched"],
                crumbles=rock.s["crumbles"],
                crumble_residual_routed=rock.s["crumbles"] > 0,
                audit={k: (v / rock.dfix if k in ("density_sum", "debris_total",
                                                  "consumed") else v)
                       for k, v in audit.items()},
                blocks_with_debris=len(rock.debris),
                blocks_with_fines=len(rock.fines),
                shed_events=sum(rock.debris_shed.values()),
                violations=len(getattr(rock, "violations_ledger", [])) +
                           len(getattr(rock, "violations_reserve", [])),
                bands=dict(b30=sum(1 for d in rock.density.values()
                                   if d // rock.dfix < 60),
                           b60_120=sum(1 for d in rock.density.values()
                                       if 60 <= d // rock.dfix < 120),
                           b120=sum(1 for d in rock.density.values()
                                    if d // rock.dfix >= 120)))


def main():
    out = {"config": {"N": 20000, "stream": "B_distributed",
                      "note": "every crumbled cell residual routed through ledger"}}
    for policy in ("hold", "shed"):
        out[policy] = run(policy)
        r = out[policy]
        print(policy, "crumbles", r["crumbles"], "| audit residual",
              r["audit"]["balance_residual"], "| drift",
              r["audit"]["tracker_drift"], "| debris",
              round(r["audit"]["debris_total"], 1), "| fines",
              round(r["audit"]["fines_total"], 1), "| consumed",
              round(r["audit"]["consumed"], 1), "| violations", r["violations"],
              flush=True)
    with open("results/e2_threshold.json", "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
