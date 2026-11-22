"""DENT Stage 0.3 — CALIB2: calibration model comparison (Models A-D).

All models run the SAME 1M-tap concentrated-ray window on the same rock
(gen_rock2(48), L=72, same alpha/fixed-point/cap base):

  Model A: alpha-scaled impacts + fixed-point density + per-tap mass cap.
  Model B: A + local fatigue softening (beta=3): repeated impacts on one spot
           soften it up to 4x, concentrating erosion where fatigue lives.
  Model B2: A + beta=8 (strong fatigue contrast).
  Model C: A + structural support coherence (erosion resistance scales with
           live lateral support; unsupported/overhanging material yields).
  Model D: A + global pacing factor: as global mass-loss fraction rises, the
           per-tap mass cap headroom grows as cap/(1-g*frac) with g=0.35 —
           the global counter NEVER creates damage; it only modulates the
           response of actually-struck material. The base cap still bounds
           the worst case, so the no-early-death bound survives.

Measured per model: removed cells, dens_sum lost, per-tap budget, max
solid run (depth) along the tap axis, rejected, sev, seconds, hash.

Output: out/s03_calib2_results.json
"""
import json, math, os, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3

SEED = 4242


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def make_rock(model, lattice=72):
    verts, tris = gen_rock2(48)
    rock = R3.RockDensity(verts, tris, lattice=lattice, dfix=65536)
    dsum = sum(rock.density.values()) / rock.dfix
    cells0 = len(rock.density)
    d0mean = dsum / cells0
    cap = (d0mean - 30.0) * cells0 / 1e9
    rock.cap_mass = cap
    rock.alpha = cap / 15.33
    rock.calib = dict(cells0=cells0, dens_sum0=dsum, d0mean=round(d0mean, 3),
                      cap_mass=cap, alpha=round(rock.alpha, 8))
    if model == "B":
        rock.beta = 3.0
    elif model == "B2":
        rock.beta = 8.0
    elif model == "C":
        rock.support = True
    elif model == "D":
        rock.pacing = 0.35
        rock._use_d = True
    return rock


def eff_cap(rock, model):
    """Model D pacing: effective per-tap cap grows as global mass is lost.
    base cap otherwise; cap never ceases to bound the erosion rate."""
    base = rock.cap_mass
    if model != "D":
        return base
    frac = 1.0 - (sum(rock.density.values()) / rock.dfix) / rock.calib["dens_sum0"]
    if frac <= 0:
        return base
    # only accelerate when erosion has passed 10% of capacity (g=0.35)
    g = 0.35
    return min(base * 4.0, base / (1.0 - g * frac)) if frac > 0.10 else base


def max_solid_run(rock, rays):
    """Deepest contiguous solid run along the concentrated ray axis (cells)."""
    L = rock.L
    vd = rays[0][1]
    ln = math.sqrt(sum(c * c for c in vd)); u = [c / ln for c in vd]
    tgt = rays[0][0]
    perp = (-u[1], u[0], 0.0)
    perp2 = (u[1] * u[2], -u[0] * u[2], u[0]**2 + u[1]**2)
    ln2 = math.sqrt(sum(x*x for x in perp2)) or 1
    perp2 = [x / ln2 for x in perp2]
    deepest = 0
    for q in range(-3, 4):
        for r2 in range(-3, 4):
            p = [tgt[a] + q * 0.03 * perp[a] + r2 * 0.03 * perp2[a] for a in range(3)]
            depth_cells = 0
            for s in range(0, 800):
                wx, wy, wz = p[0] + s * 0.25 * u[0], p[1] + s * 0.25 * u[1], p[2] + s * 0.25 * u[2]
                ii, jj, kk = int((wx - rock.origin) / rock.cs), int((wy - rock.origin) / rock.cs), int((wz - rock.origin) / rock.cs)
                if not (0 <= ii < L and 0 <= jj < L and 0 <= kk < L):
                    break
                if (ii, jj, kk) in rock.density:
                    depth_cells += 1
                    if depth_cells > deepest:
                        deepest = depth_cells
                elif depth_cells:
                    break
    return deepest


def run_model(model, n_taps=1_000_000, ray_patch=40):
    rock = make_rock(model)
    rnd = random.Random(SEED)
    acc = 0
    t0 = time.time()
    rays = []
    for q in range(ray_patch):
        vd = (0.35 + 0.01 * (q % 5) - 0.02, -0.25 + 0.01 * (q // 5) - 0.02, 0.91)
        rays.append(((0.35, 0.30, 0.0), vd))
    i = 0
    check_every = 50_000
    while acc < n_taps and rock.density:
        if model == "D" and acc % check_every == 0 and acc:
            rock.cap_mass = eff_cap(rock, model)
        tgt, vd = rays[i % len(rays)]; i += 1
        o, d = ray_into(rock, tgt, vd)
        r = rock.tap_ray(o, d)
        if r["ok"]:
            acc += 1
    deepest = max_solid_run(rock, rays)
    seconds = time.time() - t0
    dfix = rock.dfix
    dens = rock.density
    return dict(model=model, accepted=acc, cells0=rock.calib["cells0"],
                cells_left=len(dens), cells_lost=rock.calib["cells0"] - len(dens),
                dens_sum_lost=round(rock.calib["dens_sum0"] - sum(dens.values()) / dfix, 1),
                per_tap_budget=round((rock.calib["dens_sum0"] - sum(dens.values()) / dfix) / max(1, acc), 6),
                cap=rock.cap_mass, alpha=round(rock.alpha, 8), beta=rock.beta,
                support=rock.support, pacing=getattr(rock, "pacing", 0.0),
                rejected=rock.s["rejected"], sev_total=rock.s["sev_total"],
                first_removal_tap=rock.attr["first_removal_tap"],
                max_solid_run_cells=deepest,
                seconds=round(seconds, 1),
                hash=rock.hash_state())


def main():
    out = {"config": dict(n_taps=1_000_000, L=72, seed=SEED,
                          note="scratch machine, cores shared with history runs; timings indicative only"),
           "models": []}
    for model in ["A", "B", "B2", "C", "D"]:
        r = run_model(model)
        out["models"].append(r)
        print(model, json.dumps({k: r[k] for k in
              ("accepted", "cells_lost", "per_tap_budget", "sev_total", "first_removal_tap", "max_solid_run_cells", "seconds")}), flush=True)
    json.dump(out, open("out/s03_calib2_results.json", "w"), indent=1)
    print("calib2 done", flush=True)


if __name__ == "__main__":
    main()
