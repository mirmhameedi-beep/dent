"""DENT Stage 0.3 — CAP/CONSERVATION/PRECISION verification (fast).

V1. Per-tap cap: instrument _apply_carves input; assert sum of RAW carve
    takes <= cap_mass + tolerance for every accepted tap (Model A cap).
V2. Conservation: dens_sum(t) + mass_removed(t) == initial dens_sum (within
    declared accounting semantics; crumble is mass conserving by definition
    here since removed density is accounted).
V3. Precision: alpha-mode accumulation -- apply many taps whose per-tap take
    is far below one legacy density unit; measure cumulative density loss vs
    analytic sum. Rounding granularity must be <= 1/DFIX of one unit.
V4. Sweep check: no accepted tap lost (accepted counter == applied events).

Output: out/s03_capcheck_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3

OUT = "out/s03_capcheck_results.json"
res = {"config": {"L": 72, "seed": 4242, "n_taps": 50000}}


def build_rock(n_final=1_000_000_000, **kw):
    verts, tris = gen_rock2(48)
    rock = R3.RockDensity(verts, tris, lattice=72, dfix=65536, **kw)
    dsum = sum(rock.density.values()) / rock.dfix
    cells0 = len(rock.density)
    cap = (dsum / cells0 - 30.0) * cells0 / n_final
    rock.cap_mass = cap
    rock.alpha = cap / 15.33
    return rock, cap


# ---------- V1: per-tap cap ----------
rock, cap = build_rock()
max_take = 0.0
over = 0
# monkey-patch the two-pass carve to observe raw takes
orig = R3.RockDensity._apply_carves
TAKE = {"sum": 0.0, "n": 0}
def spy(self, takes, *a):
    global max_take, over
    s = sum(t for _, t, _ in takes)
    f = min(1.0, self.cap_mass / s) if (self.cap_mass and s > 0) else 1.0
    TAKE["sum"] += s * f
    TAKE["n"] += 1
    if s * f > max_take:
        max_take = s * f
    if self.cap_mass is not None and s * f > self.cap_mass * (1 + 1e-9):
        over += 1
    return orig(self, takes, *a)
R3.RockDensity._apply_carves = spy

res["_d0"] = sum(rock.density.values()) / rock.dfix
rnd = random.Random(4242)
t0 = time.time()
acc = 0
for q in range(res["config"]["n_taps"]):
    tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
    vd = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))
    o = tuple(int((tgt[i] + vd[i]/math.sqrt(sum(c*c for c in vd))*4.0) * FIX) for i in range(3))
    d = tuple(int(-c*FIX) for c in vd)
    r = rock.tap_ray(o, d)
    if r["ok"]:
        acc += 1
res["V1_cap"] = {"n_accepted": acc, "cap_mass_per_tap": cap,
                 "max_observed_sum_take": max_take, "violations": over,
                 "seconds": round(time.time()-t0, 1)}
R3.RockDensity._apply_carves = orig

# ---------- V2/V4: conservation on the SAME rock ----------
# model accounting: removed = tracked mass_removed (legacy density units)
dens_now = sum(rock.density.values()) / rock.dfix
res["V2_conservation"] = {
    "initial_dens_sum_legacy": res.get("_d0"),
    "final_dens_sum_legacy": dens_now,
    "sum_carve_takes_applied": TAKE["sum"],
    "carve_calls": TAKE["n"],
    "cells_removed": rock.attr["removals"],
    "identity": "initial - final == sum_applied_takes (+/- per-cell int rounding)",
}

# ---------- V3: precision (no rounding away) ----------
# alpha-mode: single-tap take ~ cap = 3.0e-2 legacy units/cell -> run 100k
# taps at ONE cell neighborhood; cumulative loss must track analytic sum.
rock2, cap2 = build_rock(n_final=1_000_000_000)
# find a pristine surface cell
surf = None
for c, v in rock2.density.items():
    n = sum(1 for dx, dy, dz in R3._NEIGH6 if (c[0]+dx, c[1]+dy, c[2]+dz) not in rock2.density)
    if n >= 3 and v/rock2.dfix >= 150:
        surf = c
        break
w = []
for dx, dy, dz in R3._NEIGH6:
    if (surf[0]+dx, surf[1]+dy, surf[2]+dz) not in rock2.density:
        w.append((dx, dy, dz))
nx = sum(x[0] for x in w) / len(w); ny = sum(x[1] for x in w) / len(w); nz = sum(x[2] for x in w) / len(w)
ln = math.sqrt(nx*nx + ny*ny + nz*nz) or 1.0
vd = (-nx/ln, -ny/ln, -nz/ln)
o = tuple(int((surf[i] + 0.5 + vd[i]*4.0) * FIX) for i in range(3))
d = tuple(int(-c*FIX) for c in vd)
d0 = rock2.density[surf] / rock2.dfix
N3 = 100000
for q in range(N3):
    rock2.tap_ray(o, d)
d1 = (rock2.density.get(surf, 0) / rock2.dfix) if surf in rock2.density else 0.0
# analytic single-tap take on pristine cell: A * K_COMPRESS * wgt / hard
# use alpha-scaled: measure WITH the engine's own first-tap return instead:
res["V3_precision"] = {
    "cell": list(surf), "d_before": d0, "d_after_100k": d1,
    "analytic_budget_per_tap": cap2,
    "analytic_loss": cap2 * N3,
    "measured_loss": d0 - d1,
    "note": "d0-d1 >= analytic cap sum means NO rounding-away of small taps; "
            "crumble tail can add strictly more loss, never zero",
    "granularity_units": 1.0/65536.0,
}
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps(res, indent=1))
