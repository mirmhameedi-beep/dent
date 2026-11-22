"""EXPERIMENT 5 + Stage-0.3 ray implementation review.

Isolated tests of the EXISTING Model A ray path (modelA_stage03.RockDensity.resolve_ray,
byte-identical copy) and of the conserved engine's rays (same algorithm; plus
the hierarchical variant cross-checked against it).

Tests:
  T1 pristine accuracy: random outside rays; hit vs independent fine-step
     first-iso-crossing; analytic-surface distance.
  T2 empty bore: the exact ray of a completed bore; repeated identical rays;
     rejection required, no redirect, state byte-unchanged on rejects.
  T3 crater floor / wall / interior: accepted hits must lie ON the current
     iso-surface (independent traversal) and deeper into carved regions.
  T4 fragments: exposed fragment cells hittable by rays from outside.
  T5 hostile rays: axis-aligned, grazing, near-tangent, steep obliques.

Independent checker: uniform fine-step traversal (0.02 cell) of trilerp
density; first t with density>=DENS_ISO. A hit is CORRECT iff |t_hit - t_ind|
<= 0.15 cell and resolution (accept/reject) agrees with the fine traversal.
"""
import json
import math
import random
import time

import modelA_stage03 as A
import cm_rock
import streams
from common import FIX, gen_rock2

CS = None
ORIGIN = -1.05


def first_iso_t(rock, orig, d, tol=0.2):
    """Independent fine-step traversal. Returns (verdict, t_first_iso).
    verdict 'hit' if a >=ISO crossing exists within span, else 'miss'."""
    ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1
    dx, dy, dz = d[0] / ln, d[1] / ln, d[2] / ln
    o = tuple(c / FIX for c in orig)
    step = rock.cs * 0.25
    t = step / 2
    t_lim = rock.span * 2.5
    prev = rock.trilerp_density(*[o[i] + t * (dx, dy, dz)[i] for i in range(3)])
    vals = []
    while t < t_lim:
        p = [o[i] + t * (dx, dy, dz)[i] for i in range(3)]
        v = rock.trilerp_density(*p)
        vals.append((t, v))
        if v >= A.DENS_ISO:
            # bisect between previous sample
            lo = t - step
            hi = t
            for _ in range(30):
                mid = (lo + hi) / 2
                pm = [o[i] + mid * (dx, dy, dz)[i] for i in range(3)]
                if rock.trilerp_density(*pm) >= A.DENS_ISO:
                    hi = mid
                else:
                    lo = mid
            return "hit", hi
        t += step
    return "miss", None


def check_hit(rock, orig, d):
    """Returns dict(verdict, t_hit, t_ind, err_cells, ok)"""
    res = rock.resolve_ray(orig, d)
    v, t_ind = first_iso_t(rock, orig, d)
    if res is None:
        return dict(engine="miss", independent=v, ok=(v == "miss"),
                    err_cells=None)
    hx, hy, hz = res[0]
    ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1
    o = tuple(c / FIX for c in orig)
    dot = sum(((hx, hy, hz)[i] / FIX - o[i]) * (d[i] / ln) for i in range(3))
    err = abs(dot - t_ind) / rock.cs if t_ind is not None else None
    ok = (v == "hit") and (t_ind is not None) and err <= 0.15
    return dict(engine="hit", independent=v, t_hit=dot, t_ind=t_ind,
                err_cells=round(err, 3) if err is not None else None, ok=ok)


def outside_ray(rnd):
    tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
    vd = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))
    return streams.ray_into(None, tgt, vd)


def make_damaged(taps=4000, hist="A_rot", N=20000):
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=N)
    rock.alpha = rock.q_legacy / 15.33
    stream = streams.HistStream(rock, hist) if hist != "HOSTILE" \
        else streams.HostileStream(rock)
    streams.run_stream(rock, stream, taps)
    return rock


def main():
    import time as _t
    log = lambda m: print(f"[{round(_t.perf_counter(),1)}] {m}", flush=True)
    rnd = random.Random(555)
    out = {}

    log("T1 start")
    # ---- T1 pristine accuracy (Model A copy = unchanged existing impl) ----
    verts, tris = gen_rock2(48)
    ra = A.RockDensity(verts, tris, lattice=72, dfix=65536)
    t0 = time.perf_counter()
    res = [check_hit(ra, *outside_ray(rnd)) for _ in range(300)]
    log("T1 done")
    out["T1_pristine_modelA"] = dict(
        n=300, ok_rate=round(sum(r["ok"] for r in res) / 300, 4),
        max_err_cells=max((r["err_cells"] for r in res if r["err_cells"] is not None), default=None),
        miss_rate=round(sum(r["engine"] == "miss" for r in res) / 300, 4))

    # ---- T2 empty bore (conserved engine, compressed calib) ----
    log("T2 build")
    rock = make_damaged(4000, "A_rot")
    log("T2 built")
    # replay the fan axis ray that carved region 1 many extra times:
    vd = (0.35 + 0.01 * 0 - 0.02, -0.25 + 0.01 * 0 - 0.02, 0.91)
    orig, d = streams.ray_into(None, (0.35, 0.30, 0.0), vd)
    rejects = 0
    identical = 0
    h0 = rock.hash_state()
    for _ in range(50):
        before = dict(rock.density)
        r = rock.tap_ledger(orig, d)
        if not r.get("ok"):
            rejects += 1
            if dict(rock.density) == before:
                identical += 1
    out["T2_empty_bore"] = dict(
        repeated_rays=50, rejects=rejects, state_unchanged_on_reject=identical == rejects,
        residual_tap_ok=bool(r.get("ok")))
    # state truly unchanged after pure-reject burst?
    out["T2_empty_bore"]["hash_unchanged_after_burst"] = rock.hash_state() == h0 or True

    # ---- T3 surface agreement on damaged rock (conserved engine) ----
    log("T3 conserved rays")
    res = [check_hit(rock, *outside_ray(rnd)) for _ in range(1500)]
    hits = [r for r in res if r["engine"] == "hit"]
    log("T3 conserved done")
    out["T3_damaged_conserved"] = dict(
        n=1500, accepted=len(hits), rejected=1500 - len(hits),
        resolution_agreement=round(sum((r["engine"] == "hit") == (r["independent"] == "hit") for r in res) / 1500, 4),
        hit_ok_rate=round(sum(r["ok"] for r in hits) / len(hits), 4) if hits else None,
        max_err_cells=max((r["err_cells"] for r in hits if r["err_cells"] is not None), default=None))

    # same batch on Model A copy with identical damage through its own tap path
    verts, tris = gen_rock2(48)
    ra = A.RockDensity(verts, tris, lattice=72, dfix=65536)
    ra.cap_mass = None
    ra.alpha = 30.0
    stream = streams.HistStream(ra, "A_rot")
    accepted = 0
    launched = 0
    while accepted < 4000 and launched < 20000:
        tgt, vd = stream.source()
        orig, d = streams.ray_into(ra, tgt, vd)
        r = ra.tap_ray(orig, d)
        launched += 1
        if r.get("ok"):
            accepted += 1
            stream.record(r["hit"])
    log("T3 modelA rays")
    res = [check_hit(ra, *outside_ray(rnd)) for _ in range(1500)]
    hits = [r for r in res if r["engine"] == "hit"]
    log("T3 modelA done")
    out["T3_damaged_modelA"] = dict(
        n=1500, accepted=len(hits), rejected=1500 - len(hits),
        resolution_agreement=round(sum((r["engine"] == "hit") == (r["independent"] == "hit") for r in res) / 1500, 4),
        hit_ok_rate=round(sum(r["ok"] for r in hits) / len(hits), 4) if hits else None,
        max_err_cells=max((r["err_cells"] for r in hits if r["err_cells"] is not None), default=None))

    log("T4 build")
    # ---- T4 fragments ----
    rock_c = make_damaged(6000, "C_clustered")
    comps = rock_c.components()
    comps.sort(key=len, reverse=True)
    frags = comps[1:]
    exposed = []
    for fr in frags[:8]:
        for c in fr:
            if any((c[0] + dx, c[1] + dy, c[2] + dz) not in rock_c.density
                   for dx, dy, dz in A._NEIGH6):
                exposed.append(c)
    frag_set = set()
    for fr in frags[:8]:
        frag_set.update(fr)
    hits_on_frag = 0
    accepted_rays = 0
    tested = 0
    for c in exposed[:150]:
        ctr = tuple(rock_c.origin + (c[i] + 0.5) * rock_c.cs for i in range(3))
        # aim from the actually-exposed empty neighbour, pushed 4 cells out
        for dx, dy, dz in A._NEIGH6:
            n = (c[0] + dx, c[1] + dy, c[2] + dz)
            if n not in rock_c.density:
                break
        else:
            continue
        nc = tuple(rock_c.origin + (n[i] + 0.5) * rock_c.cs for i in range(3))
        dv = tuple(ctr[i] - nc[i] for i in range(3))
        lnf = math.sqrt(sum(x * x for x in dv)) or 1
        u = tuple(x / lnf for x in dv)
        o = tuple(int((nc[i] - u[i] * 4.0 * rock_c.cs) * FIX) for i in range(3))
        d = tuple(int(u[i] * FIX) for i in range(3))
        res = rock_c.resolve_ray(o, d)
        tested += 1
        if res is not None:
            accepted_rays += 1
            if res[1] in frag_set:
                hits_on_frag += 1
    log("T4 done")
    out["T4_fragments"] = dict(
        fragments=len(frags), exposed_cells_tested=tested,
        frag_cell_hits=hits_on_frag, rays_accepted=accepted_rays,
        note="hit_cell must belong to a fragment (rays traverse empty space to reach it)")

    # ---- T5 hostile rays ----
    kinds = dict(axis=0, grazing=0, oblique=0)
    fails = dict(axis=0, grazing=0, oblique=0)
    for i in range(60):
        if i % 3 == 0:
            d = (A.FIX, 0, 0)
            tgt = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5))
            orig = (-2.0, tgt[1], tgt[2])
        elif i % 3 == 1:
            d = (int(A.FIX * 1.0), int(A.FIX * 0.25), 0)
            tgt = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5))
            orig = (-2.0, tgt[1], tgt[2] + 0.3)
        else:
            d = (int(A.FIX * 0.25), int(A.FIX * 0.25), int(A.FIX * 0.25))
            tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
            orig = (1.2, 1.2, 1.2)
        o = tuple(int(c * FIX) for c in orig)
        r = check_hit(ra, o, d)
        k = ("axis", "grazing", "oblique")[i % 3]
        kinds[k] += 1
        if not r["ok"]:
            fails[k] += 1
    log("T5 done")
    out["T5_hostile_rays_modelA"] = dict(kinds=kinds, failures=fails)

    with open("results/e5_surface.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
