"""PART A - Correct visible-surface ray resolution.

States: pristine + damaged states built on the AUTHENTIC recovered initial
rock (Part F) through MaprimRock.tap_transaction (old DDA ray path during
damage, mirroring the original POC), then two resolvers compared as PURE
functions on identical frozen states:

  old:  modelA_stage03.RockDensity.resolve_ray  (DDA + trilerp bisection)
  new:  maprim_rock.resolve_iso                 (node-plane walk + exact cubic
         per segment + bisection; never redirects)
  ref:  maprim_rock.first_iso_reference         (independent fine-step scanner
         on ref_trilerp; the adjudicator - a separate algorithm)

Metrics per family and overall: n, accepted, rejected, verdict-agreement,
false hits, false misses, error vs reference in cells (median/p95/p99/max),
% within 0.15 cells; plus sub-ISO-hit fraction for the old resolver
(reproducing the E5b finding that most accepted hits sit below ISO).
"""
import json
import math
import pickle
import random
import statistics
import time

import modelA_stage03 as A
import maprim_rock as M
import streams
from streams import ray_into

FIX = A.FIX
CS_CELLS = None   # set in main (rock.cs)


def unit(vd):
    ln = math.sqrt(sum(c * c for c in vd)) or 1.0
    return tuple(c / ln for c in vd)


def aim(rock, tgt, vd, out_dist=4.0):
    u = unit(vd)
    return (tuple(int((tgt[i] + u[i] * out_dist) * FIX) for i in range(3)),
            tuple(int(-u[i] * FIX) for i in range(3)))


def err_cells(rock, orig, d, t_new, t_ref):
    return abs(t_new - t_ref) / rock.cs


class PerFam:
    def __init__(self):
        self.n = 0
        self.acc_new = 0
        self.rej_new = 0
        self.acc_old = 0
        self.rej_old = 0
        self.acc_ref = 0
        self.false_hits = 0     # engine hit where ref says miss
        self.false_misses = 0   # engine miss where ref says hit
        self.fh_old = 0
        self.fm_old = 0
        self.errs_new = []
        self.errs_old = []
        self.sub_iso_old = 0    # old-resolver accepted hits NOT on ISO surface
        self.sub_iso_new = 0

    def add_pair(self, ref, old, new):
        self.n += 1
        vn = new["verdict"] if new else "miss"
        vo = old["verdict"] if old else "miss"
        vr = ref["verdict"]
        if vr in ("hit", "hit_at_origin"):
            self.acc_ref += 1
        if vn == "hit":
            self.acc_new += 1
        else:
            self.rej_new += 1
        if vo == "hit":
            self.acc_old += 1
        else:
            self.rej_old += 1
        ref_hit = vr in ("hit", "hit_at_origin")
        if vn == "hit" and not ref_hit:
            self.false_hits += 1
        if vn == "miss" and ref_hit:
            self.false_misses += 1
        if vo == "hit" and not ref_hit:
            self.fh_old += 1
        if vo == "miss" and ref_hit:
            self.fm_old += 1
        if vn == "hit" and ref_hit:
            self.errs_new.append((new["t"] - ref["t"]) / CS_CELLS)
        if vo == "hit" and vr == "hit":
            self.errs_old.append((old["t"] - ref["t"]) / CS_CELLS)
        if vo == "hit" and old.get("iso_val", 240.0) < A.DENS_ISO - 1e-6:
            self.sub_iso_old += 1
        if vn == "hit" and new.get("iso_val", 240.0) < A.DENS_ISO - 1e-6:
            self.sub_iso_new += 1

    def summary(self):
        def stats(v):
            if not v:
                return dict(n=0)
            av = [abs(x) / 1.0 for x in v]
            sv = sorted(av)
            return dict(n=len(sv),
                    median=round(statistics.median(sv), 6),
                    p95=round(sv[int(0.95 * (len(sv) - 1))], 6),
                    p99=round(sv[int(0.99 * (len(sv) - 1))], 6),
                    max=round(max(sv), 6),
                    within=round(100.0 * sum(1 for x in sv if x <= 0.15)
                                 / len(sv), 3))
        return dict(n=self.n, accepted_new=self.acc_new,
                    rejected_new=self.rej_new, accepted_old=self.acc_old,
                    accepted_ref=self.acc_ref,
                    false_hits_new=self.false_hits,
                    false_misses_new=self.false_misses,
                    false_hits_old=self.fh_old, false_misses_old=self.fm_old,
                    old_sub_iso_ratio=round(self.sub_iso_old /
                                            max(1, self.acc_old), 4),
                    new_sub_iso_hits=self.sub_iso_new,
                    err_new_cells=stats(self.errs_new),
                    err_old_cells=stats(self.errs_old))


def run_family(rock, fam_name, rays, per, snap_sig):
    assert rock.hash_state() == snap_sig, "state mutated before family"
    for orig, d in rays:
        ref = M.first_iso_reference(rock, orig, d)
        new = M.resolve_iso(rock, orig, d)
        old = rock.resolve_ray(orig, d)
        # normalise shapes: resolve_ray returns (fixed_point, cell)
        if old is not None:
            (hx, hy, hz), cell = old
            wx, wy, wz = hx / FIX, hy / FIX, hz / FIX
            # old resolvers param t along unit dir from same origin
            ln = math.sqrt(sum(c * c for c in d)) or 1.0
            u = tuple(c / ln for c in d)
            ox, oy, oz = orig[0] / FIX, orig[1] / FIX, orig[2] / FIX
            # distance along ray from origin
            t_old = (wx - ox) * u[0] + (wy - oy) * u[1] + (wz - oz) * u[2]
            iso_old = M.ref_trilerp(rock.density, rock.L, rock.cs, rock.origin,
                                    wx, wy, wz, rock.dfix)
            old = dict(verdict="hit", t=t_old, iso_val=iso_old,
                       point=(wx, wy, wz))
        else:
            old = None
        if new is not None:
            iso_new = A.DENS_ISO  # by contract >= ISO at point; verify:
            wx, wy, wz = new["point"]
            iso_new = M.ref_trilerp(rock.density, rock.L, rock.cs, rock.origin,
                                    wx, wy, wz, rock.dfix)
            new = dict(new, iso_val=iso_new)
        per.add_pair(ref, old, new)
    assert rock.hash_state() == snap_sig, "state mutated by ray battery"
    return per


per_fam = {}     # name -> PerFam


def fam(name):
    if name not in per_fam:
        per_fam[name] = PerFam()
    return per_fam[name]


def build_damaged(n_rot=5000, n_cluster=6000, n_hostile=2000):
    """Build damaged states with the OLD ray path in tap_transaction."""
    states = {}
    prist = M.load_pristine()
    for name, hist, n_taps in (("D1_bores", "A_rot", n_rot),
                               ("D2_fragments", "C_clustered", n_cluster),
                               ("D3_hostile", None, n_hostile)):
        rock = M.MaprimRock(prist, N=20000, debris_policy="hold", kappa=0.5)
        rock.alpha = rock.q_legacy / 15.33
        st = streams.HistStream(rock, hist, seed=4242) if hist else None
        if st is None:
            st = streams.HostileStream(rock, seed=4242)
        accepted_rays = []
        launched = 0
        while rock.s["taps"] < n_taps and launched < 40 * n_taps:
            tgt, vd = st.source()
            orig, d = ray_into(rock, tgt, vd)
            r = rock.tap_transaction(orig, d, use_iso_ray=False)
            launched += 1
            if r.get("ok"):
                st.record(r["hit"])
                accepted_rays.append((orig, d))
        states[name] = dict(rock=rock, accepted_rays=accepted_rays,
                            crumbles=rock.s["crumbles"])
        print("  built", name, "accepted", rock.s["taps"], "launched",
              launched, "crumbles", rock.s["crumbles"], flush=True)
    return states


def main():
    t00 = time.perf_counter()
    prist = M.load_pristine()

    # 0) reference-field equivalence on 2000 random points
    rock0 = M.MaprimRock(prist, N=None)
    global CS_CELLS
    CS_CELLS = rock0.cs
    rng = random.Random(31337)
    mx = 0.0
    for _ in range(2000):
        x = rng.uniform(rock0.origin - 0.1, rock0.origin + rock0.span + 0.1)
        y = rng.uniform(rock0.origin - 0.1, rock0.origin + rock0.span + 0.1)
        z = rng.uniform(rock0.origin - 0.1, rock0.origin + rock0.span + 0.1)
        mx = max(mx, abs(rock0.trilerp_density(x, y, z)
                         - M.ref_trilerp(rock0.density, rock0.L, rock0.cs,
                                         rock0.origin, x, y, z, rock0.dfix)))
    print("field equivalence max diff:", mx, flush=True)

    print("building damaged states...", flush=True)
    states = build_damaged()
    # deep-bore variant of D1: replay 3 bore rays 60x each
    rockD1 = states["D1_bores"]["rock"]
    deep = states["D1_bores"]["accepted_rays"][:3]
    for k, (orig, d) in enumerate(deep):
        for _ in range(60):
            rockD1.tap_transaction(orig, d, use_iso_ray=False)
    print("  deepened bores; crumbles now", rockD1.s["crumbles"], flush=True)
    states["D1b_deep_bores"] = dict(rock=rockD1,
                                    accepted_rays=states["D1_bores"]
                                    ["accepted_rays"][:3])

    # save damaged states snapshot signature + pickles (for reuse in C/E)
    for nm, sd in states.items():
        with open(f"../renders/state_{nm}_summary.json", "w") as f:
            json.dump(dict(cells=len(sd["rock"].density),
                           crumbles=sd["rock"].s["crumbles"],
                           hash=sd["rock"].hash_state()), f)
        with open(f"../renders/state_{nm}.pkl", "wb") as f:
            pickle.dump(sd["rock"].__dict__, f)

    # ---------------- ray battery ----------------
    out = dict(meta=dict(purpose="PART A ray resolution battery",
                         field_equiv_max_diff=mx,
                         note="reference = independent 0.05-cell fine-step "
                              "scanner on ref_trilerp (separate impl)",
                         started=time.strftime("%Y-%m-%d %H:%M:%S")))
    sig0 = rock0.hash_state()

    # F1 pristine surface
    rock = rock0
    cx = rock.origin + rock.span / 2
    rng = random.Random(555)
    rays = []
    surf = [c for c in list(rock.density)[:20000]
            if sum(1 for dx, dy, dz in A._NEIGH6
                   if (c[0] + dx, c[1] + dy, c[2] + dz) in rock.density) <= 4]
    for _ in range(300):
        c = rng.choice(surf)
        tgt = tuple(rock.origin + (c[i] + 0.5) * rock.cs
                    for i in range(3))
        vd = tuple(tgt[i] - cx + rng.uniform(-0.15, 0.15) for i in range(3))
        rays.append(ray_into(rock, tgt, vd))
    fam("F1_pristine_surface")
    run_family(rock, "F1", rays, fam("F1_pristine_surface"), sig0)
    print("F1 done", flush=True)

    # per-state families
    for nm, sd in ((k, v) for k, v in states.items() if k != "D1_bores"):
        rock = sd["rock"]
        sig = rock.hash_state()
        cx = rock.origin + rock.span / 2
        dens = rock.density
        cells = list(dens)

        def lows():     # crater-floor-like: low-but-visible cells
            return [c for c in cells if dens[c] // rock.dfix < 200]

        # F2 crater floors / walls: aim at sub-200 visible cells
        rng = random.Random(777)
        rc = 0
        rays = []
        lc = sorted(lows(), key=lambda c: dens[c])
        if lc:
            for _ in range(300):
                c = rng.choice(lc[:len(lc) // 2 + 1])
                tgt = tuple(rock.origin + (c[i] + 0.5) * rock.cs
                            for i in range(3))
                vd = tuple(tgt[i] - cx + rng.uniform(-0.1, 0.1)
                           for i in range(3))
                rays.append(ray_into(rock, tgt, vd))
                rc += 1
                if rc >= 300:
                    break
        fam(nm + "_F2_floor")
        run_family(rock, nm, rays, fam(nm + "_F2_floor"), sig)
        print(nm, "F2 done", len(rays), flush=True)

        # F3 bore-axis replay (deep bore / open hole / through rays)
        rays = list(dict.fromkeys(sd["accepted_rays"]))[:250]
        long_rays = []
        for orig, d in rays:
            # push origin back to make a longer ray (through-shots)
            u = unit(d)
            o2 = tuple(int((orig[i] / FIX - u[i] * 3.0) * FIX)
                       for i in range(3))
            long_rays.append((o2, d))
        fam(nm + "_F3_boreaxis")
        run_family(rock, nm, rays + long_rays, fam(nm + "_F3_boreaxis"), sig)
        print(nm, "F3 done", flush=True)

        # F4 exposed fragment/interior cells (few-neighbour cells aimed from
        #    a direction through the exposing opening; jitter)
        rng = random.Random(999)
        exposed = [c for c in cells[:40000]
                   if sum(1 for dx, dy, dz in A._NEIGH6
                          if (c[0] + dx, c[1] + dy, c[2] + dz) in dens) <= 2]
        rays = []
        for _ in range(250):
            if not exposed:
                break
            c = rng.choice(exposed)
            tgt = tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))
            vd = tuple(rng.uniform(-1, 1) for _ in range(3))
            rays.append(ray_into(rock, tgt, vd))
        fam(nm + "_F4_exposed")
        run_family(rock, nm, rays, fam(nm + "_F4_exposed"), sig)
        print(nm, "F4 done", flush=True)

        # F5 grazing + oblique on current surface cells
        rng = random.Random(1111)
        rays = []
        nrm = []
        for c, val in list(dens.items())[:30000]:
            if val // rock.dfix < A.DENS_ISO:
                continue
            n6 = sum(1 for dx, dy, dz in A._NEIGH6
                     if (c[0] + dx, c[1] + dy, c[2] + dz) in dens)
            if n6 <= 5:
                nrm.append(c)
        for _ in range(150):
            c = rng.choice(nrm)
            cxl = rock.origin + (c[0] + 0.5) * rock.cs
            cyl = rock.origin + (c[1] + 0.5) * rock.cs
            czl = rock.origin + (c[2] + 0.5) * rock.cs
            # outward dir ~ radial from centre; grazing = perturb strongly
            base = (cxl - cx, cyl - cx, czl - cx)
            bu = unit(base)
            per = (rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9),
                   rng.uniform(-0.9, 0.9))
            vd = tuple(-bu[i] + 0.08 * per[i] for i in range(3))  # grazing
            rays.append(ray_into(rock, (cxl, cyl, czl), vd))
        for _ in range(150):
            c = rng.choice(nrm)
            cxl = rock.origin + (c[0] + 0.5) * rock.cs
            cyl = rock.origin + (c[1] + 0.5) * rock.cs
            czl = rock.origin + (c[2] + 0.5) * rock.cs
            base = unit((cxl - cx, cyl - cx, czl - cx))
            # oblique: 60-80 deg off the inward normal
            ang = rng.uniform(1.05, 1.4)
            per = (rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))
            pu = unit(per)
            vd = tuple(-math.cos(ang) * base[i] + math.sin(ang) * pu[i]
                       for i in range(3))
            rays.append(ray_into(rock, (cxl, cyl, czl), vd))
        fam(nm + "_F5_grazing_oblique")
        run_family(rock, nm, rays, fam(nm + "_F5_grazing_oblique"), sig)
        print(nm, "F5 done", flush=True)

    # aggregate
    agg = {k: v.summary() for k, v in per_fam.items()}
    tot = PerFam()
    for v in per_fam.values():
        tot.n += v.n
        tot.acc_new += v.acc_new
        tot.rej_new += v.rej_new
        tot.acc_old += v.acc_old
        tot.rej_old += v.rej_old
        tot.acc_ref += v.acc_ref
        tot.false_hits += v.false_hits
        tot.false_misses += v.false_misses
        tot.fh_old += v.fh_old
        tot.fm_old += v.fm_old
        tot.sub_iso_old += v.sub_iso_old
        tot.sub_iso_new += v.sub_iso_new
        tot.errs_new.extend(v.errs_new)
        tot.errs_old.extend(v.errs_old)
    # rescale per-family errors: delta-t in world units -> cells with rock.cs
    def mul(d, f):
        if "n" not in d or d.get("n", 0) == 0:
            return d
        return {k: (v * f if isinstance(v, float) else v) for k, v in d.items()}
    overall = tot.summary()
    out["families"] = agg
    out["overall"] = overall
    out["wall_s"] = round(time.perf_counter() - t00, 1)
    with open("../results/a_surface.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(overall, indent=1))


if __name__ == "__main__":
    main()
