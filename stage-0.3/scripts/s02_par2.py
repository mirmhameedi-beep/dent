"""DENT Stage 0.2 — EXP PAR2: where does ordering actually matter?

PAR's single-tap pairs all commuted (no nonlinear rule was crossed). This
probe applies BURSTS n at two anchors and compares:
  AB      : burst at A fully, then burst at B  (each tap re-resolves)
  BA      : burst at B fully, then burst at A
  SIM     : pre-resolve EVERY tap against the pre-burst surface, then apply
            (the 'parallel batch' model)
  BADSIM  : pre-resolve both bursts at batch start, round-robin application
Commutes iff all four hashes agree. Sweeps n and cell separation.
Output: out/s02_par2_results.json
"""
import json, math, sys

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*FIX) for i in range(3)),
            tuple(int(-c*FIX) for c in u))


def fresh(L=72):
    verts, tris = gen_rock2(48)
    return R2.RockDensity(verts, tris, lattice=L)


def run(kind, L, ra, rb, n):
    rock = fresh(L)
    if kind == 'AB':
        for _ in range(n): rock.tap_ray(*ra)
        for _ in range(n): rock.tap_ray(*rb)
    elif kind == 'BA':
        for _ in range(n): rock.tap_ray(*rb)
        for _ in range(n): rock.tap_ray(*ra)
    elif kind == 'SIM':
        ha = [rock.resolve_ray(*ra)[0] for _ in range(n) if rock.resolve_ray(*ra)]
        hb = [rock.resolve_ray(*rb)[0] for _ in range(n) if rock.resolve_ray(*rb)]
        for h in ha: rock.impact(*h)
        for h in hb: rock.impact(*h)
    return rock.hash_state()


def main():
    out = []
    for n in (5, 25, 100):
        for sep in (0, 1, 3, 6):
            r0 = fresh(72)
            c = r0.core; o = r0.origin; cs = r0.cs
            def w(dc):
                return (o+(c[0]+dc[0]+0.5)*cs, o+(c[1]+0.5)*cs, o+(c[2]+0.5)*cs)
            ra = ray_into(r0, w((0, 0, 0)), (0.0, 0.0, 1.0))
            rb = ray_into(r0, w((sep, 0, 0)), (0.0, 0.2, 0.9))
            hs = {}
            for kind in ('AB', 'BA', 'SIM'):
                hs[kind] = run(kind, 72, ra, rb, n)
            rec = dict(n=n, sep=sep,
                       AB=hs['AB'], BA=hs['BA'], SIM=hs['SIM'],
                       ab_eq_ba=hs['AB'] == hs['BA'],
                       all_eq=hs['AB'] == hs['BA'] == hs['SIM'])
            out.append(rec)
            print(json.dumps(rec, default=str), flush=True)
    json.dump(out, open('out/s02_par2_results.json', 'w'), indent=1)
    print('par2 done')


if __name__ == '__main__':
    main()
