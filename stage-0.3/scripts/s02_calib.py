"""DENT Stage 0.2 — EXP CALIB: can the engine be calibrated to the 1e9 target?

Measured fact (s02_completion): at current constants, distributed load fully
depletes the 151k-cell rock after ~2.3M accepted taps (~0.2% of 1e9).

Two calibration candidates, both measured on real rocks (no shortcuts):

 C1  integer-swallow check: scale damage by alpha=2.3e6/1e9 with density kept
     at int 0..240 per tap resolution. Prediction: per-tap take < 0.5 unit is
     rounded away -> ZERO depletion (integer swallowing). A tap must always
     leave SOME bounded residual to accumulate.

 C2  fixed-point density at 1/4096 resolution (32-bit accumulators), all
     damage constants scaled by alpha*4096 in fixed units. Prediction: slope
     ~ taps/cell rises by 1/alpha (no swallow), 300k-tap window loses a
     measurable number of cells, extrapolated depletion lands near 1e9.

Output: out/s02_calib_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2
import s02_rock as R2


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*65536) for i in range(3)),
            tuple(int(-c*65536) for c in u))


def distributed(rock, n_taps, rst=4242):
    rnd = random.Random(rst)
    acc = 0; curve = []; t0 = time.time(); batch = max(1, n_taps//20)
    for q in range(1, n_taps+1):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        o, d = ray_into(rock, tgt, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
                                    rnd.uniform(0.5, 1.1)))
        if rock.tap_ray(o, d)["ok"]:
            acc += 1
        if q % batch == 0:
            curve.append(dict(q=q, accepted=acc, cells=len(rock.density)))
    return dict(launched=n_taps, accepted=acc, cells_left=len(rock.density),
                seconds=round(time.time()-t0, 1), curve=curve)


def slope_taps_per_cell(curve):
    a0, c0 = curve[0]["accepted"], curve[0]["cells"]
    a1, c1 = curve[-1]["accepted"], curve[-1]["cells"]
    if c0 == c1:
        return None
    return (a1-a0)/(c0-c1)


def main():
    out = {}
    verts, tris = gen_rock2(48)
    # ---- C1: alpha-scaled integer density (expect ZERO depletion/swallow)
    alpha = 0.002308263
    k0, kb0 = R2.K_COMPRESS, R2.K_BOND
    try:
        R2.K_COMPRESS = k0 * alpha
        R2.K_BOND = kb0 * alpha
        rock = R2.RockDensity(verts, tris, lattice=72)
        cells0 = len(rock.density)
        r1 = distributed(rock, 60_000)
        s1 = slope_taps_per_cell(r1["curve"])
        out["C1_integer_alpha"] = dict(cells0=cells0, cells_left=r1["cells_left"],
                                       accepted=r1["accepted"],
                                       slope=s1, seconds=r1["seconds"],
                                       zero_depletion=bool(r1["cells_left"] == cells0))
        print("C1 done", out["C1_integer_alpha"], flush=True)
    finally:
        R2.K_COMPRESS, R2.K_BOND = k0, kb0

    # ---- C2: fixed-point x4096, scaled constants
    import s02_mt as MT_ISO
    try:
        SC2 = 4096
        R2.DENS_MAX = 240 * SC2
        R2.DENS_FAIL = 30 * SC2
        R2.DENS_ISO = 120 * SC2
        MT_ISO.ISO = 120 * SC2                    # extractor has its own copy
        R2.K_COMPRESS = 2.6 * alpha * SC2          # ~24.6 fixed units at w=1
        R2.K_BOND = 90 * alpha
        rock2 = R2.RockDensity(verts, tris, lattice=72)
        cells0 = len(rock2.density)
        r2 = distributed(rock2, 300_000)
        s2 = slope_taps_per_cell(r2["curve"])
        cu = r2["curve"]
        # use the LAST 60% of the curve for the steady-state slope
        late = cu[len(cu)*2//5:]
        s2l = slope_taps_per_cell(late)
        dep = None
        if s2l:
            dep = int(s2l * late[-1]["cells"])
        out["C2_fixedpoint"] = dict(cells0=cells0, cells_left=r2["cells_left"],
                                    accepted=r2["accepted"],
                                    slope_full=s2, slope_late=s2l,
                                    derived_depletion=dep,
                                    target=1_000_000_000,
                                    hits_target=bool(dep and 0.5e9 < dep < 2.5e9),
                                    seconds=r2["seconds"])
        print("C2 done", out["C2_fixedpoint"], flush=True)
    finally:
        R2.DENS_MAX, R2.DENS_FAIL, R2.DENS_ISO = 240, 30, 120
        MT_ISO.ISO = 120
        R2.K_COMPRESS, R2.K_BOND = k0, kb0

    json.dump(out, open("out/s02_calib_results.json", "w"), indent=1)
    print("calib done")


if __name__ == "__main__":
    main()
