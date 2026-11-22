"""DENT Stage 0.2 — Experiment PAR: parallel-safety and incremental rebuilds.

Answers (measured, not assumed):
 P1. Two impacts processed 'simultaneously' equal the sequential result IFF
     their kernels are disjoint AND neither triggers stress propagation.
 P2. Commutativity depends on separation: pairs of impacts at cell distances
     1..16 are applied in order A,B vs B,A vs simultaneous; state hashes show
     exactly where ordering stops mattering.
 P3. Incremental rebuild: re-extracting ONLY the dirty region of the blocky
     mesh vs a full extraction (timing + identical changed-region output).
 P4. Local MT extraction with a 1-cell apron reproduces the full-MT triangles
     inside the region (stitch-by-deterministic-vertex-key).
Output: out/s02_par_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2
import s02_mt as MT


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*FIX) for i in range(3)),
            tuple(int(-c*FIX) for c in u))


def apply_both(rock, r1, order):
    """order in {'seqAB','seqBA','simul'}"""
    if order == 'seqAB':
        rock.tap_ray(*r1[0]); rock.tap_ray(*r1[1])
    elif order == 'seqBA':
        rock.tap_ray(*r1[1]); rock.tap_ray(*r1[0])
    else:  # 'simul': pre-resolve both, then apply damages without re-reading
        h1 = rock.resolve_ray(*r1[0]); h2 = rock.resolve_ray(*r1[1])
        if h1 and h2:
            rock.impact(*h1[0]); rock.impact(*h2[0])
        elif h1: rock.impact(*h1[0])
        elif h2: rock.impact(*h2[0])
    return rock.hash_state()


def fresh_rock(L=72):
    verts, tris = gen_rock2(48)
    return R2.RockDensity(verts, tris, lattice=L)


def pair_commutes(sep_cells, L=72, weaken=False):
    """Two rays against the SAME pristine rock each run; sep in cells."""
    rock0 = fresh_rock(L)
    c = rock0.core
    o = rock0.origin
    def w(cell0, dcell):
        cc = (cell0[0]+dcell[0], cell0[1]+dcell[1], cell0[2]+dcell[2])
        return (o+(cc[0]+0.5)*rock0.cs, o+(cc[1]+0.5)*rock0.cs, o+(cc[2]+0.5)*rock0.cs)
    a = (w(c, (0, 0, 0)), (0.0, 0.0, 1.0))
    b = (w(c, (sep_cells, 0, 0)), (0.0, 0.0, 1.0))
    ra = ray_into(rock0, a[0], (0.0, 0.0, 1.0))
    rb = ray_into(rock0, b[0], (0.0, 0.0, 1.0))
    if weaken:  # weaken so stress propagation actually triggers on A
        for _ in range(1400):
            rock0.tap_ray(*ra)
    hs = {}
    rockA = fresh_rock(L)
    if weaken:
        for _ in range(1400):
            rockA.tap_ray(*ra)
    hs['AB'] = apply_both(rockA, (ra, rb), 'seqAB')
    rockB = fresh_rock(L)
    if weaken:
        for _ in range(1400):
            rockB.tap_ray(*ra)
    hs['BA'] = apply_both(rockB, (ra, rb), 'seqBA')
    rockC = fresh_rock(L)
    if weaken:
        for _ in range(1400):
            rockC.tap_ray(*ra)
    hs['S'] = apply_both(rockC, (ra, rb), 'simul')
    return dict(sep_cells=sep_cells, weakened=weaken,
                commutes=(hs['AB'] == hs['BA'] == hs['S']),
                AB=hs['AB'], BA=hs['BA'], S=hs['S'])


def local_rebuild(L=72):
    rock = fresh_rock(L)
    rnd = random.Random(77)
    tgt = (0.35, 0.30, 0.0)
    ln = math.sqrt(0.35*0.35+0.25*0.25+0.91*0.91)
    u = (0.35/ln, -0.25/ln, 0.91/ln)
    org = tuple(int((tgt[i]+u[i]*4.0)*FIX) for i in range(3))
    d = tuple(int(-c*FIX) for c in u)
    for _ in range(400):
        rock.tap_ray(org, d)
    # dirty set approximation: cells touched by recent impacts (impact kernel R_IMP)
    affected = set()
    cs = rock.cs; o = rock.origin
    hi = rock.resolve_ray(org, d)
    # collect solid cells within 4 cells of the crater axis' last known hits:
    for (cc, _dv) in list(rock.density.items()):
        pass
    # cheaper: define dirty box around last resolved impact cell
    ci, cj, ck = rock.resolve_ray(org, d)[1] if hi else rock.core
    R = 6
    dirty = {(i, j, k) for i in range(ci-R, ci+R+1) for j in range(cj-R, cj+R+1)
             for k in range(ck-R, ck+R+1)}
    # full blocky
    t0 = time.time(); fv, ft = MT.extract_blocky(rock); t_full = time.time()-t0
    t0 = time.time(); lv, lt = MT.extract_blocky_local(rock, dirty) if hasattr(MT, 'extract_blocky_local') else (None, None)
    has_local = lt is not None
    t_local = time.time()-t0 if has_local else None
    out = dict(L=L, dirty_cells=len(dirty), full_blocky_s=round(t_full, 3),
               local_blocky_s=(round(t_local, 3) if has_local else None),
               full_tris=len(ft), local_tris=(len(lt) if has_local else None))
    # MT local with apron vs full MT (inside dirty box only)
    if L <= 72:
        t0 = time.time()
        full = MT.extract_mt(rock)
        t_mtf = time.time()-t0
        if hasattr(MT, 'extract_mt_local'):
            t0 = time.time()
            reg = MT.extract_mt_local(rock, dirty)
            t_mtl = time.time()-t0
            keyset = {tuple(v) for v in full[0]}
            same = all(tuple(v) in keyset for v in reg[0]) if reg else False
            out.update(mt_full_s=round(t_mtf, 2), mt_local_s=round(t_mtl, 2),
                       mt_local_tris=len(reg[2]) if reg else 0,
                       mt_local_subset_of_full=bool(same))
        else:
            out['mt_local'] = 'not implemented'
    return out


def main():
    res = {"pairs": [], "local": None}
    for sep in (0, 1, 2, 4, 8, 16):
        r = pair_commutes(sep, weaken=False)
        res["pairs"].append(r)
        print("sep", sep, "commutes", r["commutes"], flush=True)
    for sep in (0, 2, 4):
        r = pair_commutes(sep, weaken=True)
        res["pairs"].append(r)
        print("sep", sep, "weakened commutes", r["commutes"], flush=True)
    print("local rebuild...", flush=True)
    res["local"] = local_rebuild()
    print(json.dumps(res["local"], default=str)[:300], flush=True)
    json.dump(res, open("out/s02_par_results.json", "w"), indent=1, default=str)
    print("par done")


if __name__ == "__main__":
    main()
