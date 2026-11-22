"""PART B - One authoritative per-tap material budget.

B1  Reproduce the suspected double-budget flaw in the ORIGINAL conserved
    ledger implementation (cm_rock.py, copied unchanged): _apply_carves
    creates a LOCAL budget from self.q_tap, while debris_after_tap creates
    a SECOND fresh budget `self.q_tap - 0` inside the same accepted tap.
    Instrumented externally (no code modification): per-tap consumption =
    delta of rock.consumed across tap_ledger.
B2  Show _check_invariant is log-only: violations recorded, taps committed.
B3  Corrected engine (maprim_rock.MaprimRock.tap_transaction): one shared
    budget, clamped, pre-commit validation -> per-tap spend <= q_tap.
B4  Rollback proof: fault hook injects extra consumption mid-tap; the tap
    must be rejected and state restored byte-identically.
B5  Static audit of all `consumed` writers in both implementations.

Both engines run on the AUTHENTIC recovered initial rock (Part F), same
N=20000 compressed-lifetime parameters, same stream recipe as E2.
"""
import json
import pickle
import random
import sys
import time

import cm_rock
import maprim_rock as M
import modelA_stage03 as A
import streams
from streams import ray_into

sys.path.insert(0, "/tmp/dent-poc/conserved-material")

PRISTINE = None


def recalc_conserved(rock):
    """Re-base an already-constructed ConservedRock onto the authentic
    pristine state (density dict swapped in place; all budget scalars
    recomputed exactly as the constructor would)."""
    rock.density = dict(PRISTINE["density"])
    rock.occ_init = PRISTINE["occ_init"]
    rock.boundary_init = PRISTINE["boundary_init"]
    rock.main_mass = sum(rock.density.values())
    rock.M0 = rock.main_mass
    rock.cells0 = len(rock.density)
    crumble_slack = A.DENS_FAIL * rock.cells0 * rock.dfix
    rock.Mr = max(crumble_slack + 1, int(rock.M0 * 0.02))
    rock.q_tap = (rock.M0 - rock.Mr) // rock.N
    rock.q_legacy = rock.q_tap / rock.dfix
    rock.cap_mass = rock.q_legacy
    rock.block_count = {}
    for (i, j, k) in rock.density.keys():
        b = (i // cm_rock.HB, j // cm_rock.HB, k // cm_rock.HB)
        rock.block_count[b] = rock.block_count.get(b, 0) + 1
    rock.mat_cache = {}
    rock.fatigue = {}
    rock.bdamage = {}
    rock.severed = set()
    rock.s = dict(taps=0, rejected=0, fragments=[], sev_total=0,
                  mass_removed=0, mass_applied=0, crumbles=0)
    return rock


def b1_original_double_budget(n_target=6000):
    verts, tris = (None, None)
    stub = __import__("s01_c")            # unchanged cm_rock constructor path
    from common import gen_rock2
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000,
                                 debris_policy="shed")
    recalc_conserved(rock)
    rock.alpha = rock.q_legacy / 15.33    # compressed-lifetime recipe (E2)
    stream = streams.HistStream(rock, "B_distributed", seed=4242)
    rng = random.Random(1)
    q = rock.q_tap
    per_tap = []
    over = []
    shed_ev_taps = []
    prev_shed = 0
    launched = 0
    t0 = time.perf_counter()
    while rock.s["taps"] < n_target and launched < 40 * n_target:
        tgt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
               rng.uniform(-0.6, 0.6))
        vd = (0.0, 0.0, 1.0)
        # use the deterministic B_distributed recipe
        tgt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
               rng.uniform(-0.6, 0.6))
        vd = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
              rng.uniform(0.5, 1.1))
        orig, d = ray_into(rock, tgt, vd)
        c0 = rock.consumed
        r = rock.tap_ledger(orig, d)
        if r.get("ok"):
            spend = rock.consumed - c0
            n = rock.s["taps"]
            per_tap.append(spend)
            if spend > q:
                over.append(dict(tap=n, spend=spend, q_tap=q,
                                 ratio=spend / q))
            if sum(rock.debris_shed.values()) > prev_shed:
                prev_shed = sum(rock.debris_shed.values())
                shed_ev_taps.append((n, spend))
        launched += 1
    wall = time.perf_counter() - t0
    return dict(
        engine="cm_rock.ConservedRock (original, unchanged code)",
        rock="authentic recovered pristine (Part F)",
        N=20000, q_tap_dfix=q, q_tap_legacy=q / rock.dfix,
        alpha=rock.alpha, accepted=rock.s["taps"], launched=launched,
        wall_s=round(wall, 1),
        n_over_taps=len(over), over_examples=over[:12],
        max_spend=max(per_tap), max_spend_over_q=max(per_tap) / q,
        mean_spend=sum(per_tap) / len(per_tap),
        total_consumed=rock.consumed,
        nq_line_n=rock.s["taps"], nq_line=rock.s["taps"] * q,
        consumed_over_nq=rock.consumed > rock.s["taps"] * q,
        violations_allowance=len(getattr(rock, "violations_allowance", [])),
        violations_allowance_examples=getattr(rock, "violations_allowance",
                                              [])[:5],
        violations_reserve=len(getattr(rock, "violations_reserve", [])),
        violations_ledger=len(getattr(rock, "violations_ledger", [])),
        crumbles=rock.s["crumbles"],
        debris_total=sum(rock.debris.values()),
        fines_total=sum(rock.fines.values()),
        recent_shed_events=shed_ev_taps[-12:],
        n_shed_events=sum(rock.debris_shed.values()),
    )


def b3_corrected_single_budget(n_target=6000):
    rock = M.MaprimRock(M.load_pristine(), N=20000, debris_policy="shed",
                        kappa=0.5)
    rock.alpha = rock.q_legacy / 15.33
    q = rock.q_tap
    rng = random.Random(1)   # same stream recipe/seeding as B1
    per_tap = []
    over = []
    rolled = []
    launched = 0
    t0 = time.perf_counter()
    while rock.s["taps"] < n_target and launched < 40 * n_target:
        tgt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
               rng.uniform(-0.6, 0.6))
        vd = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
              rng.uniform(0.5, 1.1))
        orig, d = ray_into(rock, tgt, vd)
        c0 = rock.consumed
        r = rock.tap_transaction(orig, d, use_iso_ray=False)
        if r.get("ok"):
            spend = rock.consumed - c0
            per_tap.append(spend)
            if spend > q:
                over.append(dict(tap=rock.s["taps"], spend=spend, q_tap=q))
        elif r.get("reason") == "invariant_violation_rolled_back":
            rolled.append(dict(tap=r["tap"], violations=r["violations"]))
        launched += 1
    wall = time.perf_counter() - t0
    return dict(
        engine="maprim_rock.MaprimRock (corrected single budget)",
        N=20000, q_tap_dfix=q, q_tap_legacy=q / rock.dfix,
        alpha=rock.alpha, accepted=rock.s["taps"], launched=launched,
        wall_s=round(wall, 1),
        n_over_taps=len(over), over_examples=over[:12],
        max_spend=max(per_tap) if per_tap else 0,
        max_spend_over_q=(max(per_tap) / q) if per_tap else 0,
        mean_spend=(sum(per_tap) / len(per_tap)) if per_tap else 0,
        total_consumed=rock.consumed,
        nq_line=rock.s["taps"] * q,
        consumed_over_nq=rock.consumed > rock.s["taps"] * q,
        rolled_back=len(rolled), rolled_examples=rolled[:5],
        crumbles=rock.s["crumbles"],
        debris_total=sum(rock.debris.values()),
        fines_total=sum(rock.fines.values()),
        n_shed_events=sum(rock.debris_shed.values()),
    )


def b4_rollback_proof():
    rock = M.MaprimRock(M.load_pristine(), N=20000, debris_policy="shed")
    rock.alpha = rock.q_legacy / 15.33

    def snap():
        return dict(hash=rock.hash_state(),
                    consumed=rock.consumed, burned=rock.burned,
                    main_mass=rock.main_mass,
                    debris_total=sum(rock.debris.values()),
                    fines_total=sum(rock.fines.values()),
                    severed=len(rock.severed),
                    cells=len(rock.density), taps=rock.s["taps"])

    def new_ray():
        tgt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
               rng.uniform(-0.6, 0.6))
        vd = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6),
              rng.uniform(0.5, 1.1))
        return ray_into(rock, tgt, vd)

    rng = random.Random(7)
    n_ok, n_miss = 0, 0
    while n_ok < 50:                       # warm up: clean taps
        orig, d = new_ray()
        r = rock.tap_transaction(orig, d, use_iso_ray=False)
        if r["ok"]:
            n_ok += 1
        else:
            n_miss += 1
    warm = dict(clean_accepted=n_ok, misses_rejected=n_miss)
    pre = snap()

    def inject_use(rock, phase):
        rock.consumed += rock.q_tap            # bogus extra consumption
    n_miss = 0
    while True:
        orig, d = new_ray()
        r = rock.tap_transaction(orig, d, fault_hook=inject_use,
                                 use_iso_ray=False)
        if r.get("reason") == "miss_rejected":
            n_miss += 1
            if n_miss > 100:
                break
            continue
        break
    post = snap()
    identical1 = all(pre[k] == post[k] for k in pre)
    fault1 = dict(pre=pre,
                  fault_result=dict(ok=r.get("ok"), reason=r.get("reason"),
                                    violations=r.get("violations")),
                  post=post, state_identical=identical1,
                  misses_skipped=n_miss)

    def inject2(rock, phase):
        rock._tx["used_carve"] += rock.q_tap * 2
    pre2 = snap()
    n_miss = 0
    while True:
        orig, d = new_ray()
        r2 = rock.tap_transaction(orig, d, fault_hook=inject2,
                                  use_iso_ray=False)
        if r2.get("reason") == "miss_rejected":
            n_miss += 1
            if n_miss > 100:
                break
            continue
        break
    post2 = snap()
    identical2 = all(pre2[k] == post2[k] for k in pre2)
    r3 = rock.tap_transaction(orig, d, use_iso_ray=False)
    return dict(warmup=warm,
                fault1=fault1,
                fault2=dict(pre=pre2,
                            result=dict(ok=r2.get("ok"), reason=r2.get("reason"),
                                        violations=r2.get("violations")),
                            post=post2, state_identical=identical2,
                            misses_skipped=n_miss),
                clean_tap_after=dict(ok=r3.get("ok"), reason=r3.get("reason")))


def b5_writer_audit():
    import re
    audit = {}
    src = {}
    for name in ("cm_rock.py", "maprim_rock.py"):
        with open(name) as f:
            src[name] = f.read().splitlines()
    for name, lines in src.items():
        hits = []
        for i, ln in enumerate(lines, 1):
            if re.search(r"\bconsumed\b", ln):
                hits.append(f"{name}:{i}: {ln.strip()}")
        audit[name] = hits
    return audit


def main():
    global PRISTINE
    PRISTINE = M.load_pristine()
    out = dict(
        meta=dict(purpose="PART B per-tap budget audit",
                  rock_sha_note="see results/f_initial_rock.json",
                  stream="B_distributed recipe, random.Random(1) per side",
                  time=time.strftime("%Y-%m-%d %H:%M:%S")),
    )
    print("B1 original double-budget reproduction...", flush=True)
    out["b1_original"] = b1_original_double_budget()
    o = out["b1_original"]
    print("  accepted=%d over-q taps=%d max/q=%.3f log-only-violations=%d"
          % (o["accepted"], o["n_over_taps"], o["max_spend_over_q"],
             o["violations_allowance"]), flush=True)
    print("B3 corrected single budget...", flush=True)
    out["b3_corrected"] = b3_corrected_single_budget()
    c = out["b3_corrected"]
    print("  accepted=%d over-q taps=%d max/q=%.3f rolled=%d"
          % (c["accepted"], c["n_over_taps"], c["max_spend_over_q"],
             c["rolled_back"]), flush=True)
    print("B4 rollback proof...", flush=True)
    out["b4_rollback"] = b4_rollback_proof()
    print("  fault1 identical=%s fault2 identical=%s clean_after=%s"
          % (out["b4_rollback"]["fault1"]["state_identical"],
             out["b4_rollback"]["fault2"]["state_identical"],
             out["b4_rollback"]["clean_tap_after"]["ok"]), flush=True)
    print("B5 writer audit...", flush=True)
    out["b5_writer_audit"] = b5_writer_audit()
    with open("../results/b_budget_audit.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote results/b_budget_audit.json", flush=True)


if __name__ == "__main__":
    main()
