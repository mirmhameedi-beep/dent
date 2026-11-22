"""DENT Stage 0.2 — EXP VIS: final visual comparisons.

V1. Equal-history pair: TWO fresh L=72 rocks, 10,000 accepted taps each,
    one concentrated, one distributed. Rendered identically (same camera).
    -> tap_count identical, geometry visibly different.
V2. Destruction sequence: one L=72 rock eroded via distributed load, renders
    captured at ~10/25/50/75/90% cell depletion.
V3. Interior cavity close-up: crater floor + hammered interior wall.
Output: out/s02/VS_*.png + out/s02_vis_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2
import s02_mt as MT
import s02_render as RD

OUT = "out/s02"


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*65536) for i in range(3)),
            tuple(int(-c*65536) for c in u))


def render(rock, name, size=460):
    mv, mn, mt = MT.extract_mt(rock)
    wv = [(round(x*65536), round(y*65536), round(z*65536)) for x, y, z in mv]
    RD.render_mesh(wv, mt, f"{OUT}/{name}_front.png", view=(0.35, -0.35, 0.88),
                   zoom=1.5, size=size)
    RD.render_mesh(wv, mt, f"{OUT}/{name}_34.png", view=(0.62, 0.5, 0.7),
                   zoom=1.0, size=size)
    return dict(verts=len(mv), tris=len(mt))


def main():
    res = {}
    verts, tris = gen_rock2(48)

    # V1: equal 10k-tap histories
    def accept_n(rays, n):
        ok = 0; guard = 0
        while ok < n and guard < 4*n:
            guard += 1
            for (o, d) in rays:
                if ok >= n: break
                if rock_silent.tap_ray(o, d)["ok"]:
                    ok += 1
        return ok

    # concentrated: 40 rays inside a ~1.2-cell-radius patch (small region)
    # NOTE: a single ray self-limits at bore-through (~1.7k taps at L=72);
    # 'one small area' means a patch, so use a round-robin of clustered rays.
    import math as _m
    rockC = R2.RockDensity(verts, tris, lattice=72)
    raysC = []
    for a in range(40):
        t, s = divmod(a, 5)
        dx = (s-2)*0.2
        dy = (t-1)*0.2
        vd = (0.35+dx, -0.25+dy, 0.91)
        ln = _m.sqrt(sum(c*c for c in vd))
        raysC.append(ray_into(rockC, (0.35, 0.30, 0.0),
                              tuple(c/ln*1.0018 for c in vd)))
    okC = 0; gi = 0
    while okC < 10000 and gi < 400_000:
        gi += 1
        if rockC.tap_ray(*raysC[gi % len(raysC)])["ok"]:
            okC += 1
    res["V1_concentrated"] = dict(accepted=okC, cells=len(rockC.density))
    res["V1_concentrated_render"] = render(rockC, "VS_concentrated10k")
    # distributed
    rockD = R2.RockDensity(verts, tris, lattice=72)
    rnd = random.Random(555)
    raysD = []
    for _ in range(400):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
        raysD.append(ray_into(rockD, tgt, (rnd.uniform(-0.6, 0.6),
                                           rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))))
    okD = 0; guard = 0
    while okD < 10000 and guard < 200_000:
        guard += 1
        o, d = raysD[guard % len(raysD)]
        if rockD.tap_ray(o, d)["ok"]:
            okD += 1
    res["V1_distributed"] = dict(accepted=okD, cells=len(rockD.density))
    res["V1_distributed_render"] = render(rockD, "VS_distributed10k")
    json.dump(res, open("out/s02_vis_results.json", "w"), indent=1, default=str)
    print("V1 done", json.dumps(res["V1_concentrated"]), json.dumps(res["V1_distributed"]), flush=True)

    # V3: interior cavity close-up (crater 1200 + mouth ray + hammer 400)
    rockV = R2.RockDensity(verts, tris, lattice=72)
    ra = ray_into(rockV, (0.40, 0.25, 0.0), (0.5, -0.2, 0.85))
    acc = 0
    for _ in range(1200):
        if rockV.tap_ray(*ra)["ok"]:
            acc += 1
    # mouth ray (reuse the found tilt)
    ra2 = ray_into(rockV, (0.40, 0.25, 0.0), (0.5117419495, -0.1967766716, 0.8363008541))
    for _ in range(400):
        rockV.tap_ray(*ra2)
    res["V3_cavity"] = dict(accepted_setup=acc, cells=len(rockV.density))
    mv, mn, mt = MT.extract_mt(rockV)
    wv = [(round(x*65536), round(y*65536), round(z*65536)) for x, y, z in mv]
    RD.render_mesh(wv, mt, f"{OUT}/VS_cavity_interior_front.png",
                   view=(0.35, -0.35, 0.88), zoom=2.2, size=560,
                   target=(0.25/FIX if False else 0.25, 0.2, 0.05))
    RD.render_mesh(wv, mt, f"{OUT}/VS_cavity_interior_34.png", view=(0.62, 0.5, 0.7),
                   zoom=2.0, size=560, target=(0.25, 0.2, 0.05))
    res["V3_cavity_render"] = dict(verts=len(mv), tris=len(mt))
    json.dump(res, open("out/s02_vis_results.json", "w"), indent=1, default=str)
    print("V3 done", json.dumps(res["V3_cavity"]), flush=True)

    # V2: destruction sequence (distributed depletion; renders at thresholds)
    rockX = R2.RockDensity(verts, tris, lattice=72)
    cells0 = len(rockX.density)
    rndx = random.Random(4242)
    shots = [0.10, 0.25, 0.50, 0.75, 0.90]
    done = set(); t0 = time.time(); accx = 0
    for q in range(3_500_000):
        tgt = (rndx.uniform(-0.6, 0.6), rndx.uniform(-0.6, 0.6), rndx.uniform(-0.6, 0.6))
        o, d = ray_into(rockX, tgt, (rndx.uniform(-0.6, 0.6), rndx.uniform(-0.6, 0.6),
                                     rndx.uniform(0.5, 1.1)))
        if rockX.tap_ray(o, d)["ok"]:
            accx += 1
        cells = len(rockX.density)
        frac = 1.0 - cells / cells0
        for s in list(shots):
            if s not in done and frac >= s:
                done.add(s)
                key = f"VS_destroy_{int(s*100)}pct"
                res[key] = dict(accepted=accx, cells=cells,
                                depletion=round(frac, 3),
                                minutes=round((time.time()-t0)/60, 1))
                res[key+"_render"] = render(rockX, key)
                json.dump(res, open("out/s02_vis_results.json", "w"), indent=1, default=str)
                print(key, "accepted", accx, "cells", cells, flush=True)
        if len(done) == len(shots) or cells == 0:
            break
    print("vis done", flush=True)


if __name__ == "__main__":
    main()
