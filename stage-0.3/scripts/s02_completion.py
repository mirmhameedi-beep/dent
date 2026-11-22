"""DENT Stage 0.2 — EXP COMP: the one-billion-tap completion problem.

Measures, on real rocks (no prescribed cuts):
 1. Distributed-erosion depletion curve: cells(rock) vs accepted-taps until
    exhaustion; and total accepted taps until the rock has NO targetable
    surface (or a hard cap). This decides whether current constants would
    complete far before 1 billion under distributed load.
 2. Pathological (single-ray) load: taps are self-limiting by bore-through;
    rock is NOT consumed by concentration alone.
 3. Calibration check: rerun the distributed load with per-tap damage scaled
    by alpha so the measured depletion count would land near the product
    target — verifies the linear-scaling hypothesis alpha = N_measured/1e9
    on a shorter run, and quantifies the 'visible per tap' trade-off.
Output: out/s02_completion_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*FIX) for i in range(3)),
            tuple(int(-c*FIX) for c in u))


def distributed_stream(rock, n_taps, cap_no_target=True, rst=4242):
    rnd = random.Random(rst)
    accepted = 0; curve = []; t0 = time.time()
    batch = max(1, n_taps // 40)
    for q in range(n_taps):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        o, d = ray_into(rock, tgt, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
                                    rnd.uniform(0.5, 1.1)))
        r = rock.tap_ray(o, d)
        if r["ok"]:
            accepted += 1
        if (q+1) % batch == 0:
            curve.append(dict(q=q+1, accepted=accepted, cells=len(rock.density)))
            # stop early if nothing left
            if len(rock.density) == 0:
                break
        if not rock.density:
            break
    return dict(launched=n_taps, accepted=accepted, cells_left=len(rock.density),
                seconds=round(time.time()-t0, 1), curve=curve,
                hash=rock.hash_state())


def main():
    out = {"depletion_distributed": None, "calibration": None,
           "pathological_single_ray": None}
    # 1. distributed depletion on L=72
    verts, tris = gen_rock2(48)
    rock = R2.RockDensity(verts, tris, lattice=72)
    cells0 = len(rock.density)
    print("L72 cells0", cells0, flush=True)
    r = distributed_stream(rock, 300_000)
    r["cells0"] = cells0
    out["depletion_distributed"] = r
    # derive depletion count: linear fit on the curve
    cu = r["curve"]
    if len(cu) >= 3:
        a0 = cu[0]["accepted"]; c0 = cu[0]["cells"]
        a1 = cu[-1]["accepted"]; c1 = cu[-1]["cells"]
        if c0 != c1:
            slope = (a1-a0)/(c0-c1)          # taps accepted per cell lost
            out["derived_taps_per_cell_lost"] = round(slope, 4)
            out["derived_full_depletion_taps"] = int(slope * c0)
    print(json.dumps({k: v for k, v in out.items() if k != "depletion_distributed"}
                     | {"acc": r["accepted"], "cells_left": r["cells_left"]}), flush=True)

    # 2. single-ray pathological on a fresh rock
    rock2 = R2.RockDensity(verts, tris, lattice=72)
    tgt = (0.35, 0.30, 0.0)
    o, d = ray_into(rock2, tgt, (0.35, -0.25, 0.91))
    ok = 0; rej_after = 0
    for q in range(200_000):
        rr = rock2.tap_ray(o, d)
        if rr["ok"]:
            ok += 1
        else:
            rej_after += 1
    out["pathological_single_ray"] = dict(
        accepted=ok, rejected=rej_after, cells_left=len(rock2.density),
        note="concentration self-limits: after bore-through the ray is rejected forever; the rock is not consumed")

    # 3. calibration probe: alpha-scaled engine on the SAME 60k taps. Expected:
    # cells lost per accepted tap scales linearly -> depletion taps ~= 1e9
    # when alpha ~= measured depletion / 1e9. Measured on a short window.
    dep = out.get("derived_full_depletion_taps") or 0
    if dep:
        alpha = dep / 1e9
        out["calibration"] = {"alpha": alpha,
                              "per_tap_density_units": round(2.6 * alpha, 6),
                              "note": ("alpha scales all damage constants; "
                                       "each cell then needs ~1e9/cells taps to crumble")}
        # VALIDATION: scale the per-tap carve by alpha and check the depletion
        # slope scales by ~1/alpha as the linear hypothesis predicts
        rock3 = R2.RockDensity(verts, tris, lattice=72)
        K0 = R2.K_COMPRESS
        try:
            R2.K_COMPRESS = K0 * alpha
            rw = distributed_stream(rock3, 40_000, rst=4242)
            slopew = None
            cu = rw["curve"]
            if len(cu) >= 3 and cu[0]["cells"] != cu[-1]["cells"]:
                a0, c0 = cu[0]["accepted"], cu[0]["cells"]
                a1, c1 = cu[-1]["accepted"], cu[-1]["cells"]
                if c0 != c1:
                    slopew = (a1-a0)/(c0-c1)
            out["calibration"]["scaled_window_slope_taps_per_cell"] = (
                round(slopew, 2) if slopew else None)
            base_slope = out["derived_taps_per_cell_lost"]
            pred = base_slope / alpha
            out["calibration"]["predicted_slope"] = round(pred, 2)
            out["calibration"]["linear_hypothesis_holds"] = bool(
                slopew and pred and abs(slopew - pred) / pred < 0.25)
        finally:
            R2.K_COMPRESS = K0
    json.dump(out, open("out/s02_completion_results.json", "w"), indent=1)
    print("comp done", flush=True)


if __name__ == "__main__":
    main()
