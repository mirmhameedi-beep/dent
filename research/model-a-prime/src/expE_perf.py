"""PART E - Reconciled performance comparison on the AUTHENTIC original rock.

E6 (Task 1) inconsistency documented: the conserved engine was constructed
with N=20000 (q_tap = 1477.02 legacy/tap) while the report quoted a
'billion-scale allowance' of 0.029540415 legacy/tap (the STUB rock's lifetime
cap (dmean-30)*cells0/1e9), and alpha = 0.00197456 = the ORIGINAL rock's
lifetime cap / 15.33. So Model A and the ledger ran with caps differing
~50,000x, and the alpha belonged to a different rock than the cap.

This re-run uses ONE documented parameterisation for all sides:
  rock     : authentic recovered pristine (Part F)
  N        : 1,000,000,000 (conceptual lifetime)
  Mr       : DENS_FAIL * cells0 * dfix + 1  (crumble slack base, 30/cell)
  q_tap    : (M0 - Mr) // N  -> ~0.030272 legacy/tap for the ledger;
             Model A gets cap_mass = the same value
  alpha    : q_tap_legacy / 15.33 (billion-scale alpha recipe)
  regime   : BILLION-ALPHA SHORT RUN (5000 accepted taps) - erosion is tiny;
             this measures per-tap COST, not lifetime evolution.
"""
import json
import resource
import time

import modelA_stage03 as A
from modelA_stage03 import DENS_FAIL
import maprim_rock as M
import streams
from streams import ray_into

FIX = 65536


def rss():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


class ModelAAudit(A.RockDensity):
    """Model A + modified-cell counting, built faithfully from the pristine
    recovery dict (no ledger)."""

    def __init__(self, pristine, cap_legacy):
        p = pristine
        self.L = p["L"]; self.origin = p["origin"]; self.span = p["span"]
        self.cs = p["cs"]; self.mat = p["mat"]
        self.alpha = None
        self.dfix = FIX
        self.no_sev = False; self.no_fat_flaw = False
        self.cap_mass = cap_legacy
        self.beta = 0.0; self.support = False
        self.grain = False; self.grain_size = 9.0
        self.grain_seed = 911
        self.attr = dict(removals=0, single_tap_kills=0,
                         pre_death_bucket=[0] * 8, take_sum=0.0,
                         fatal_takes=[], first_removal_tap=None,
                         first_sub120_tap=None, first_sub200_tap=None)
        self.density = {}
        self.bdamage = {}; self.severed = set(); self.fatigue = {}
        self.s = dict(taps=0, rejected=0, fragments=[], sev_total=0,
                      mass_removed=0, mass_applied=0, crumbles=0)
        self.times = dict(ray=0.0, impact=0.0, conn=0.0, extract=0.0)
        self.occ_init = p["occ_init"]
        self.boundary_init = p["boundary_init"]
        self._init_density()
        self._cover(3)
        self.core = self._seed_core()
        self._dirty_cells = set()
        self._mat_cache = {}
        self._sc_queue = []
        self.modified_last = 0

    def _apply_carves(self, takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc,
                      removed_now):
        n_before = 0
        total = sum(t for _, t, _ in takes)
        f = min(1.0, self.cap_mass / total) if (self.cap_mass and total > 0) \
            else 1.0
        for cell, take, dcur in takes:
            tf = take * f * self.dfix
            newd = dcur - tf
            if newd < DENS_FAIL * self.dfix:
                removed_now.append(cell)
                n_before += 1
            else:
                newd_int = int(round(newd))
                if newd_int != dcur:
                    n_before += 1
                self.density[cell] = newd_int
        self.modified_last = n_before


def bench(eng, hist, n_taps, use_txn=False, use_iso=False):
    stream = streams.HistStream(eng, hist, seed=4242)
    mod_cells = 0
    accepted = 0
    launched = 0
    txn_us = 0.0
    t0 = time.perf_counter()
    while accepted < n_taps and launched < n_taps * 4:
        tgt, vd = stream.source()
        orig, d = ray_into(eng, tgt, vd)
        if use_txn:
            t1 = time.perf_counter()
            r = eng.tap_transaction(orig, d, use_iso_ray=use_iso)
            txn_us += (time.perf_counter() - t1) * 1e6
        else:
            r = eng.tap_ray(orig, d)
        launched += 1
        if r.get("ok"):
            accepted += 1
            if hasattr(eng, "modified_last"):
                mod_cells += eng.modified_last
    wall = time.perf_counter() - t0
    return dict(hist=hist, accepted=accepted, launched=launched,
                wall_s=round(wall, 3),
                ms_per_accepted_tap=round(wall / accepted * 1000, 3),
                accepted_per_s=round(accepted / wall, 1),
                ms_per_tap_ray=round(eng.times["ray"] / accepted * 1000, 3),
                impact_ms_per_tap=round(eng.times["impact"] / accepted * 1000,
                                        3),
                txn_wall_ms_per_tap=round(txn_us / accepted / 1000, 4)
                if use_txn else None,
                rss_mb=rss(),
                cells=len(eng.density),
                severances=eng.s["sev_total"],
                crumbles=eng.s["crumbles"],
                consumed_legacy=(round(eng.consumed / eng.dfix, 3)
                                 if hasattr(eng, "consumed") else None),
                modified_cells_per_tap=round(mod_cells / accepted, 2)
                if mod_cells else 0)


def main():
    prist = M.load_pristine()
    N = 1_000_000_000
    proto = M.MaprimRock(prist, N=N, reserve_frac=0.0)
    M0 = proto.M0
    cells0 = proto.cells0
    Mr = DENS_FAIL * cells0 * FIX + 1
    q_tap = (M0 - Mr) // N
    q_legacy = q_tap / FIX
    alpha = q_legacy / 15.33
    del proto

    out = dict(
        meta=dict(purpose="PART E reconciled performance",
                  regime="BILLION-ALPHA SHORT RUN: 5000 accepted taps at "
                         "alpha = q_tap/15.33 - measures per-tap COST, NOT "
                         "lifetime evolution; do not read as billion-scale "
                         "throughput forecasts",
                  time=time.strftime("%Y-%m-%d %H:%M:%S"),
                  e6_inconsistency=dict(
                      e6_conserved_constructor="ConservedRock(N=20000) -> "
                                               "q_tap=1477.02 legacy/tap "
                                               "(stub rock)",
                      e6_reported_allowance=0.029540415,
                      e6_reported_alpha=0.00197456,
                      e6_alpha_origin="original-rock cap 0.030269998 / 15.33",
                      resolution="Model A ran cap=0.029540415, conserved ran "
                                 "cap=1477.02 (~50,000x larger); "
                                 "alpha=0.00197456 matches the ORIGINAL rock "
                                 "cap 0.030269998/15.33 not the stub cap; at "
                                 "billion-alpha demand the caps rarely/never "
                                 "bound, so CPU numbers were not invalidated "
                                 "by the cap mismatch, but the documented "
                                 "configuration was inconsistent"),
                  this_run=dict(N=N, M0_legacy=M0 / FIX, Mr_legacy=Mr / FIX,
                                cells0=cells0, q_tap_dfix=q_tap,
                                q_tap_legacy=q_legacy, alpha=alpha,
                                cap_all_sides_legacy=q_legacy)))
    cap_legacy = q_legacy
    out["sides"] = {}

    eng = ModelAAudit(prist, cap_legacy)
    eng.alpha = alpha
    for hist in ("A_concentrated", "B_distributed"):
        out["sides"]["modelA_" + hist] = bench(eng, hist, 5000)
        print("modelA", hist, "done", flush=True)
    del eng

    eng = M.MaprimRock(prist, N=N, reserve_frac=0.0, debris_policy="hold",
                       kappa=0.5, verify="incremental")
    eng.alpha = alpha
    for hist in ("A_concentrated", "B_distributed"):
        out["sides"]["maprim_ledger_" + hist] = bench(eng, hist, 5000,
                                                      use_txn=True)
        print("maprim_ledger", hist, "done", flush=True)
    del eng

    eng = M.MaprimRock(prist, N=N, reserve_frac=0.0, debris_policy="hold",
                       kappa=0.5, verify="incremental")
    eng.alpha = alpha
    for hist in ("A_concentrated", "B_distributed"):
        out["sides"]["maprim_iso_" + hist] = bench(eng, hist, 5000,
                                                   use_txn=True, use_iso=True)
        print("maprim_iso", hist, "done", flush=True)
    del eng

    eng = M.MaprimRock(prist, N=N, reserve_frac=0.0, debris_policy="hold",
                       kappa=0.5, verify="full_recount")
    eng.alpha = alpha
    out["sides"]["maprim_ledger_fullrecount_A_concentrated"] = \
        bench(eng, "A_concentrated", 5000, use_txn=True)
    print("maprim_ledger_fullrecount A_concentrated done", flush=True)
    del eng

    lh = {}
    ih = {}
    for hist in ("A_concentrated", "B_distributed"):
        a = out["sides"]["modelA_" + hist]["ms_per_accepted_tap"]
        b = out["sides"]["maprim_ledger_" + hist]["ms_per_accepted_tap"]
        c = out["sides"]["maprim_iso_" + hist]["ms_per_accepted_tap"]
        lh[hist] = dict(modelA_ms=a, maprim_ledger_ms=b,
                        delta_ms=round(b - a, 3),
                        overhead_pct=round((b - a) / a * 100, 2))
        ih[hist] = dict(maprim_ledger_ms=b, maprim_iso_ms=c,
                        delta_ms=round(c - b, 3),
                        overhead_pct=round((c - b) / b * 100, 2))
    out["ledger_overhead"] = lh
    out["iso_overhead"] = ih

    with open("../results/e_perf.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    for k, v in out["sides"].items():
        print(k, v["ms_per_accepted_tap"], "ms/tap  rss", v["rss_mb"],
              "modified", v["modified_cells_per_tap"], flush=True)
    print("ledger overhead:", json.dumps(lh))
    print("iso overhead:", json.dumps(ih))


if __name__ == "__main__":
    main()
