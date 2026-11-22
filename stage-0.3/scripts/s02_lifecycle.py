"""DENT Stage 0.2 — Experiment L: complete impact lifecycle on the density-field
rock with bond-lattice fracture. No prescribed cuts anywhere.

Runs on ONE rock (L=96):
  Phase S: repeated impacts at one broad-face location (1,10,100,1e3,1e4,3e4)
  Phase F: cavity-interior impacts (wall) — proves interior damage
Outputs: out/s02_lifecycle_results.json + PNG renders per stage.
"""
import json, math, sys, time
sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2, s02_mt as MT, s02_render as RD

OUT = "out/s02"
L = 96


def stage_stats(rock):
    low = sum(1 for v in rock.density.values() if v < R2.DENS_ISO)
    return dict(cells=len(rock.density), low_density_cells=low,
                crumbles=rock.s["crumbles"], severed=rock.s["sev_total"],
                taps=rock.s["taps"], rejected=rock.s["rejected"])


def render_stage(rock, tag, target_hit, view_ray_dir):
    mv, mn, mt = MT.extract_mt(rock)
    wv = [(round(x*FIX), round(y*FIX), round(z*FIX)) for x, y, z in mv]
    RD.render_mesh(wv, mt, f"{OUT}/LC_{tag}_front.png", view=view_ray_dir, zoom=1.6,
                   target=(target_hit[0]/FIX, target_hit[1]/FIX, target_hit[2]/FIX), size=420)
    RD.render_mesh(wv, mt, f"{OUT}/LC_{tag}_34.png", view=(0.62, 0.5, 0.7), zoom=1.0, size=420)
    RD.render_mesh(wv, mt, f"{OUT}/LC_{tag}_close.png", view=view_ray_dir, zoom=4.0,
                   target=(target_hit[0]/FIX, target_hit[1]/FIX, target_hit[2]/FIX), size=420)


def main():
    t00 = time.perf_counter()
    verts, tris = gen_rock2(48)
    rock = R2.RockDensity(verts, tris, lattice=L)
    pv, pm, pt = MT.extract_mt(rock)
    wv = [(round(x*FIX), round(y*FIX), round(z*FIX)) for x, y, z in pv]
    RD.render_mesh(wv, pt, f"{OUT}/LC_PRISTINE_front.png", view=(0.62, 0.5, 0.7), size=420)
    RD.render_mesh(wv, pt, f"{OUT}/LC_PRISTINE_34.png", view=(0.9, 0.25, 0.75), size=420)
    res = {"lattice": L, "pristine_cells": len(rock.density)}

    vd = (0.35, -0.25, 0.91)
    ln = math.sqrt(sum(c*c for c in vd)); vd = tuple(x/ln for x in vd)
    centre_world = (0.35, 0.30, 0.0)
    far = 4.0
    orig = tuple(int((centre_world[i] + vd[i]*far) * FIX) for i in range(3))
    d = tuple(int(-x*FIX) for x in vd)
    r0 = rock.resolve_ray(orig, d)
    assert r0 is not None, "anchor ray missed"
    h0 = r0[0]
    print("anchor:", [round(x/FIX, 4) for x in h0], "cell:", r0[1], flush=True)
    res["anchor"] = {"hit": h0, "cell": r0[1]}

    stages = [1, 10, 100, 1000, 10000, 30000]
    launched = 0
    for n in stages:
        t0 = time.perf_counter(); lb = launched
        miss = 0
        while rock.s["taps"] < n and launched < n*5:
            rr = rock.tap_ray(orig, d)
            launched += 1
            if not rr["ok"]:
                miss += 1
        per = (time.perf_counter()-t0)*1000/max(1, launched-lb)
        r = rock.resolve_ray(orig, d)
        depth = (math.dist([x/FIX for x in r[0]], [x/FIX for x in h0]))/rock.cs if r else None
        stats = stage_stats(rock)
        stats.update(stage=n, launched=launched, miss_after=miss,
                     ms_per_tap=round(per, 3),
                     depth_cells=round(depth, 2) if depth is not None else None,
                     through=depth is None)
        main, frags = rock.fragments()
        sizes = sorted((len(x) for x in frags), reverse=True)
        stats.update(nfrag=len(frags), frag_top=sizes[:6])
        print(f"stage {n}: {stats}", flush=True)
        res[f"S{n}"] = stats
        if n >= 100:
            tgt = r[0] if r is not None else h0
            render_stage(rock, f"S{n}", tgt, vd)
    res["final_hash"] = rock.hash_state()

    # ---------------- Phase F: cavity wall impacts -------------------------
    vd2 = list(vd); vd2[0] += 0.55; vd2[2] += 0.1
    ln2 = math.sqrt(sum(c*c for c in vd2)); vd2 = tuple(x/ln2 for x in vd2)
    orig2 = tuple(int((centre_world[i] + vd2[i]*far) * FIX) for i in range(3))
    d2 = tuple(int(-x*FIX) for x in vd2)
    r_in1 = rock.resolve_ray(orig2, d2)
    h_wall0 = r_in1[0] if r_in1 else None
    c_before = r_in1[1] if r_in1 else None
    before_low = None
    if c_before:
        ci, cj, ck = c_before
        before_low = sum(1 for ddx in (-1,0,1) for ddy in (-1,0,1) for ddz in (-1,0,1)
                         if (ci+ddx, cj+ddy, ck+ddz) in rock.density
                         and rock.density[(ci+ddx, cj+ddy, ck+ddz)] < R2.DENS_MAX-8)
    acc = 0
    for q in range(2000):
        rr = rock.tap_ray(orig2, d2)
        if rr["ok"]:
            acc += 1
    r_in2 = rock.resolve_ray(orig2, d2)
    interior_damaged = 0
    after_low = None
    if r_in2:
        ci, cj, ck = r_in2[1]
        after_low = sum(1 for ddx in (-1,0,1) for ddy in (-1,0,1) for ddz in (-1,0,1)
                        if (ci+ddx, cj+ddy, ck+ddz) in rock.density
                        and rock.density[(ci+ddx, cj+ddy, ck+ddz)] < R2.DENS_MAX-8)
        for ddx in (-1,0,1):
            for ddy in (-1,0,1):
                for ddz in (-1,0,1):
                    c = (ci+ddx, cj+ddy, ck+ddz)
                    dd = rock.density.get(c)
                    if dd is not None and dd < R2.DENS_MAX - 8:
                        interior_damaged += 1
    res["cavity_wall"] = dict(hit_before=h_wall0, cell_before=c_before,
                              low_before=before_low, hit_after=(r_in2[0] if r_in2 else None),
                              low_after=after_low, accepted_2000=acc,
                              interior_cells_damaged=interior_damaged)
    print("cavity wall:", res["cavity_wall"], flush=True)
    mv, mn, mt = MT.extract_mt(rock)
    wv2 = [(round(x*FIX), round(y*FIX), round(z*FIX)) for x, y, z in mv]
    RD.render_mesh(wv2, mt, f"{OUT}/LC_cavitywall_34.png", view=(0.62, 0.5, 0.7), zoom=1.4, size=420)
    RD.render_mesh(wv2, mt, f"{OUT}/LC_cavitywall_close.png", view=vd2, zoom=3.5,
                   target=centre_world, size=420)

    json.dump(res, open("out/s02_lifecycle_results.json", "w"), indent=1, default=str)
    print("done %.0fs" % (time.perf_counter()-t00), flush=True)
    return rock, res


if __name__ == "__main__":
    main()
