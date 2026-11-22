"""EXPERIMENT 6 - Efficiency comparison at the billion calibration.

Model A (unmodified copy, cap enabled - the production configuration) vs the
conserved ledger engine on the same deterministic streams. Measures:
wall time, per-tap phase breakdown (ray/impact), peak RSS, modified cells per
accepted tap, crumbles, structure sizes at milestones. Plus a separate
hierarchical-DDA benchmark (Option C element) on a heavily damaged state:
resolve_ray vs resolve_ray_fast (2-level block skipping), asserted to return
identical contact cells.
"""
import json
import random
import resource
import time

import modelA_stage03 as A
import cm_rock
import streams
from common import gen_rock2

CAP_BILLION = None  # per-rock derived (as in Model A calib2)
ALPHA_BILLION = 0.00197456


class ModelAAudit(A.RockDensity):
    """Model A + modified-cell counting (same measurement as the conserved
    engine's ledger routing produces)."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.modified_last = 0

    def _apply_carves(self, takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc,
                      removed_now):
        n_before = 0
        total = sum(t for _, t, _ in takes)
        f = min(1.0, self.cap_mass / total) if (self.cap_mass and total > 0) else 1.0
        for cell, take, dcur in takes:
            tf = take * f * self.dfix
            newd = dcur - tf
            if newd < A.DENS_FAIL * self.dfix:
                removed_now.append(cell)
                n_before += 1
            else:
                newd_int = int(round(newd))
                if newd_int != dcur:
                    n_before += 1
                self.density[cell] = newd_int
        self.modified_last = n_before


def rss():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def bench(eng, hist, n_taps):
    stream = streams.HistStream(eng, hist)
    rnd_h = {"A_concentrated": 4242, "B_distributed": 4242}[hist]
    mod_cells = 0
    accepted = 0
    launched = 0
    t0 = time.perf_counter()
    while accepted < n_taps and launched < n_taps * 4:
        tgt, vd = stream.source()
        orig, d = streams.ray_into(eng, tgt, vd)
        r = eng.tap_ray(orig, d)
        launched += 1
        if r.get("ok"):
            accepted += 1
            if hasattr(eng, "modified_last"):
                mod_cells += eng.modified_last
    wall = time.perf_counter() - t0
    return dict(hist=hist, accepted=accepted, launched=launched,
                wall_s=round(wall, 2),
                ms_per_tap=round(wall / n_taps * 1000, 3),
                ray_time_share=round(eng.times["ray"] /
                                     (eng.times["ray"] + eng.times["impact"] + 1e-9), 3),
                impact_ms_per_tap=round(eng.times["impact"] / n_taps * 1000, 3),
                ms_per_tap_ray=round(eng.times["ray"] / n_taps * 1000, 3),
                rss_mb=rss(),
                cells=len(eng.density),
                severances=eng.s["sev_total"],
                crumbles=eng.s["crumbles"],
                modified_cells_per_tap=round(mod_cells / n_taps, 2))


def main():
    out = {"config": {"n_taps": 5000, "alpha": ALPHA_BILLION, "lattice": 72,
                      "note": "billion calibration; Model A with per-tap cap enabled"}}
    verts, tris = gen_rock2(48)
    proto = A.RockDensity(verts, tris, lattice=72, dfix=65536)
    dmean = sum(proto.density.values()) / proto.dfix / len(proto.density)
    cap = (dmean - 30.0) * len(proto.density) / 1e9
    out["config"]["cap_mass"] = cap
    out["config"]["cells0_poc"] = len(proto.density)
    out["config"]["dens_sum0_poc"] = sum(proto.density.values()) / 65536
    del proto
    for hist in ("A_concentrated", "B_distributed"):
        verts, tris = gen_rock2(48)
        ra = ModelAAudit(verts, tris, lattice=72, dfix=65536)
        ra.cap_mass = cap
        ra.alpha = ALPHA_BILLION
        out["modelA_" + hist] = bench(ra, hist, 5000)
        del ra
        verts, tris = gen_rock2(48)
        rc = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000)
        rc.alpha = alpha = ALPHA_BILLION
        rc.cap_mass = rc.q_legacy
        b = bench(rc, hist, 5000)
        b["ledger_audit_ms"] = None
        t1 = time.perf_counter()
        rc.audit_ledger()
        b["ledger_audit_ms"] = round((time.perf_counter() - t1) * 1000, 1)
        b["debris_blocks"] = len(rc.debris)
        out["conserved_" + hist] = b
        print(hist, "done", flush=True)
    del verts, tris

    # ---- hierarchical DDA benchmark on a damaged state ----
    verts, tris = gen_rock2(48)
    rc = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000)
    rc.alpha = rc.q_legacy / 15.33
    streams.run_stream(rc, streams.HistStream(rc, "A_rot"), 4000)
    empty_blocks = sum(1 for v in rc.block_count.values() if v == 0)
    rnd = random.Random(31337)
    mismatches = 0
    n_bench = 600
    t_plain = 0.0
    t_fast = 0.0
    for _ in range(n_bench):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        vd = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))
        orig, d = streams.ray_into(rc, tgt, vd)
        t1 = time.perf_counter()
        r1 = rc.resolve_ray(orig, d)
        t_plain += time.perf_counter() - t1
        t2 = time.perf_counter()
        r2 = rc.resolve_ray_fast(orig, d)
        t_fast += time.perf_counter() - t2
        c1 = r1[1] if r1 else None
        c2 = r2[1] if r2 else None
        if c1 != c2:
            mismatches += 1
    out["hier_dda"] = dict(
        rays=n_bench, empty_blocks=empty_blocks,
        total_blocks=len(rc.block_count),
        contact_cell_mismatches=mismatches,
        plain_ms_per_ray=round(t_plain / n_bench * 1000, 4),
        fast_ms_per_ray=round(t_fast / n_bench * 1000, 4),
        speedup=round(t_plain / t_fast, 2) if t_fast else None)
    with open("results/e6_efficiency.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
