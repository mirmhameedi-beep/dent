"""DENT Stage 0.3 — EXP ATTR: component attribution of premature depletion.

Goal: identify WHICH damage mechanism kills the rock at ~2.3M accepted taps
before touching any constant, by instrumenting the real engine and running
counterfactuals:

  R1 carve-only path   : per-tap density removal (mass budget)
  fatigue path         : accumulated fatigue opening flaws (threshold 400)
  R4/R5 sever/cascade  : bond severing + stress-driven cascades

Cell loss in this engine happens ONLY via the carve-crumble path (R1 ->
density < DENS_FAIL -> removal). Severing changes topology and can enable
flaws but never removes a cell directly. The experiments therefore measure:
  (a) the removal histogram (pre-death density of removed cells; single-tap
      kills vs worn-out cells), per-tap mass budget D_mean;
  (b) timeline: first measurable carve, first sub-200, first sub-120
      (iso-visible), first removal; milestone cells/fatigue/sever stats;
  (c) counterfactual depletion slopes: NOSEV (bonds cannot sever), NOFAT
      (fatigue cannot open flaws), both vs BASE;
  (d) alpha window: engine at alpha = 0.0023 (derived 1e9-calibration) with
      DFIX=65536 -> measure density-descent rate; derive what per-tap mass
      budget would guarantee depletion at exactly ~1e9 under a linear
      hypothesis; quantify the uncertainty of that hypothesis.

Output: out/s03_attr_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3

SEED = 4242          # same stream as Stage 0.2 s02_completion (distributed)
N_LAUNCH = 300_000


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def stream(rock, n_launch, seed=SEED, milestones=(), rock_id="?"):
    """Distributed tap stream (same generator as Stage 0.2). Returns stats."""
    rnd = random.Random(seed)
    accepted = 0
    mile = sorted(milestones)
    ms_rows = []
    t0 = time.time()
    for q in range(1, n_launch + 1):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        o, d = ray_into(rock, tgt, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
                                    rnd.uniform(0.5, 1.1)))
        if rock.tap_ray(o, d)["ok"]:
            accepted += 1
        if mile and accepted >= mile[0]:
            mile.pop(0)
            ms_rows.append(history_row(rock, accepted, q))
        if not rock.density:
            break
    return dict(accepted=accepted, launched=q, ms=ms_rows,
                seconds=round(time.time() - t0, 1),
                hash=rock.hash_state())


def history_row(rock, accepted, launched):
    dens = rock.density
    n = len(dens)
    fatigue400 = sum(1 for v in rock.fatigue.values() if v > 400)
    return dict(accepted=accepted, launched=launched, cells=n,
                dens_sum=sum(dens.values()) / rock.dfix,
                severed=len(rock.severed), sev_total=rock.s["sev_total"],
                fatigue400=fatigue400, crumbles=rock.s["crumbles"],
                removed=rock.attr["removals"])


def summarise(rock, name, run, cells0):
    a = rock.attr
    row = dict(name=name, accepted=run["accepted"], launched=run["launched"],
               seconds=run["seconds"], hash=run["hash"], cells0=cells0,
               cells_left=len(rock.density),
               cells_lost=cells0 - len(rock.density),
               removed=a["removals"], crumbles=rock.s["crumbles"],
               sev_total=rock.s["sev_total"], severed_alive=len(rock.severed),
               fatigue400=sum(1 for v in rock.fatigue.values() if v > 400),
               single_tap_kills=a["single_tap_kills"],
               pre_death_bucket=a["pre_death_bucket"],
               dens_sum0=round(run["ms"][0]["dens_sum"], 1) if run["ms"] else None,
               first_removal_tap=a["first_removal_tap"],
               first_sub200_tap=a["first_sub200_tap"],
               first_sub120_tap=a["first_sub120_tap"])
    cu = [row for row in run["ms"] if row["accepted"]]
    if len(cu) >= 2 and cu[0]["cells"] != cu[-1]["cells"]:
        a0, c0 = cu[0]["accepted"], cu[0]["cells"]
        a1, c1 = cu[-1]["accepted"], cu[-1]["cells"]
        if c0 != c1:
            row["slope_taps_per_cell"] = round((a1 - a0) / (c0 - c1), 4)
            row["derived_depletion_taps"] = int((a1 - a0) / (c0 - c1) * cells0)
    if run["ms"]:
        row["ms"] = run["ms"]
    # measured per-tap mass budget (legacy density units / accepted tap)
    # from the *curve*: (dens_sum drop) per accepted tap
    if len(cu) >= 2:
        dsum0, dsum1 = cu[0]["dens_sum"], cu[-1]["dens_sum"]
        acc0, acc1 = cu[0]["accepted"], cu[-1]["accepted"]
        # dens_sum at first milestone already includes early taps; approximate
        # by taking the first milestone at accepted==first milestone value
        row["dens_sum_lost_per_tap"] = round((dsum0 - dsum1) / max(1, acc1 - acc0), 5)
    return row


def main():
    out = {"config": dict(seed=SEED, n_launch=N_LAUNCH, L=72,
                          note="scratch machine; sequential processing"),
           "runs": []}
    verts, tris = gen_rock2(48)
    MILES = (10_000, 50_000, 100_000, 150_000, 200_000, 250_000, 290_000)

    # 1. BASE — full engine, instrumented
    rock = R3.RockDensity(verts, tris, lattice=72)
    cells0 = len(rock.density)
    run = stream(rock, N_LAUNCH, milestones=MILES)
    out["runs"].append(summarise(rock, "BASE", run, cells0))
    print("BASE done", out["runs"][0].get("slope_taps_per_cell"), flush=True)

    # 2. NOSEV — bonds can never sever (isolates carve+fatigue mass path)
    rock = R3.RockDensity(verts, tris, lattice=72, no_sev=True)
    run = stream(rock, N_LAUNCH, milestones=MILES)
    out["runs"].append(summarise(rock, "NOSEV", run, cells0))
    print("NOSEV done", out["runs"][1].get("slope_taps_per_cell"), flush=True)

    # 3. NOFAT — fatigue cannot open flaws (density-flaw pathway still active)
    rock = R3.RockDensity(verts, tris, lattice=72, no_fat_flaw=True)
    run = stream(rock, N_LAUNCH, milestones=MILES)
    out["runs"].append(summarise(rock, "NOFAT", run, cells0))
    print("NOFAT done", out["runs"][2].get("slope_taps_per_cell"), flush=True)

    # 4. alpha window — real engine at the derived 1e9-calibration
    # alpha = BASE_slope / slope_target ; slope_target = 1e9/cells0
    base = out["runs"][0]
    slope_target = 1e9 / cells0
    alpha = (base.get("slope_taps_per_cell") or 15.23) / slope_target
    out["alpha"] = dict(alpha=alpha, slope_target=round(slope_target, 2),
                        per_tap_density_budget=round((DENS_MAX_BUDGET := 210) / slope_target, 6),
                        per_tap_density_budget_note="210 = DENS_MAX - DENS_FAIL legacy density units per cell")
    rock = R3.RockDensity(verts, tris, lattice=72, alpha=alpha, dfix=65536)
    run = stream(rock, 60_000, milestones=(10_000, 30_000, 50_000, 60_000))
    a_row = summarise(rock, f"ALPHA_{alpha:.6f}", run, cells0)
    # at alpha scale, the meaningful early metric is density descent:
    ms = run["ms"]
    if len(ms) >= 2:
        rate = (ms[0]["dens_sum"] - ms[-1]["dens_sum"]) / max(1, ms[-1]["accepted"] - ms[0]["accepted"])
        a_row["dens_sum_lost_per_tap"] = round(rate, 6)
        a_row["derived_depletion_from_descent"] = int(cells0 * 210 / rate) if rate > 0 else None
    out["runs"].append(a_row)
    print("ALPHA window done", a_row.get("dens_sum_lost_per_tap"),
          a_row.get("derived_depletion_from_descent"), flush=True)

    json.dump(out, open("out/s03_attr_results.json", "w"), indent=1)
    print("attr done", flush=True)


if __name__ == "__main__":
    main()
