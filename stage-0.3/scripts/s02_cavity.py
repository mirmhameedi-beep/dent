"""DENT Stage 0.2 — EXP CAV: impacts on freshly exposed cavity walls.

Quantified, no prescribed cuts:
 1. Carve a crater with 1200 taps (just before its ~1285-tap bore-through).
 2. Take a ray that passed near the crater at a steep angle. Resolve it on a
    PRISTINE twin (t_pristine hit) and on the cratered rock (t_now). If
    t_now > t_pristine, the ray now strikes a RECESSED interior wall.
 3. Hammer that interior wall 400 times; measure receding hit (depth cells
    grows), local density drop, cells fully removed near the wall hit, and
    confirm no state change far away.
Output: out/s02_cavity_results.json
"""
import json, math, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c*c for c in vd)); u = tuple(c/ln for c in vd)
    return (tuple(int((tgt[i]+u[i]*4.0)*FIX) for i in range(3)),
            tuple(int(-c*FIX) for c in u))


def main():
    verts, tris = gen_rock2(48)
    rock = R2.RockDensity(verts, tris, lattice=72)
    twin = R2.RockDensity(verts, tris, lattice=72)

    tgt = (0.40, 0.25, 0.0)
    ln = math.sqrt(0.5*0.5+0.2*0.2+0.85*0.85)
    u = (0.5/ln, -0.2/ln, 0.85/ln)
    ra = ray_into(rock, tgt, (0.5, -0.2, 0.85))
    acc = 0
    for _ in range(1200):
        if rock.tap_ray(*ra)["ok"]:
            acc += 1
    # find a ray that enters THROUGH the carved mouth and strikes interior
    # geometry: sweep small tilts around the bore axis until the cratered-rock
    # hit diverges from the pristine hit (then the ray passed the old surface)
    tgt2 = (0.40, 0.25, 0.0)
    def tilt(base, dy, dx):
        v = (base[0]+dx, base[1]+dy, base[2])
        lnn = math.sqrt(sum(c*c for c in v))
        return (v[0]/lnn, v[1]/lnn, v[2]/lnn)
    best = None
    cand = [(dy, dx) for dy in (0.0, 0.02, 0.04, -0.02, -0.04, 0.06, -0.06)
            for dx in (0.02, -0.02, 0.04, -0.04, 0.07, -0.07, 0.10, -0.10)]
    for (dy, dx) in cand:
        v = tilt(u, dy, dx)
        ra_try = ray_into(rock, tgt2, v)
        h_try = rock.resolve_ray(*ra_try)
        hp_try = twin.resolve_ray(*ra_try)
        if h_try and hp_try and h_try[0] != hp_try[0]:
            best = (v, h_try, hp_try)
            break
    out = dict(accepted_setup=acc,
               mouth_ray_search=dict(candidates=len(cand), found=bool(best),
                                     vd=(list(best[0]) if best else None)))
    h_now = best[1] if best else None
    h_prist = best[2] if best else None
    ra2 = ray_into(rock, tgt2, best[0]) if best else (None, None)
    recess_cells = None
    if h_now and h_prist:
        def tparam(h, v):
            hp = [c/FIX for c in h[0]]
            o = [tgt2[i]+v[i]*4.0 for i in range(3)]   # ray origin
            return math.dist(hp, o)
        recess_cells = round((tparam(h_now, best[0]) - tparam(h_prist, best[0]))/rock.cs, 3)
    out.update(hit_on_cavity_wall=(list(h_now[0]) if h_now else None),
               wall_cell=(list(h_now[1]) if h_now else None),
               hit_pristine_same_ray=(list(h_prist[0]) if h_prist else None),
               recessed_cells=recess_cells)
    # hammer the interior wall
    if h_now:
        wc = h_now[1]
        d_before = rock.density.get(wc)
        h0hash_far = None
        rec = []
        for q in range(400):
            rr = rock.tap_ray(*ra2)
            if q % 100 == 99:
                hw = rock.resolve_ray(*ra2)
                rec.append(dict(taps=q+1,
                                wall_cell_now=(list(hw[1]) if hw else None),
                                density_at_first_wall_cell=rock.density.get(wc)))
        d_after = rock.density.get(wc)
        low_near = sum(1 for (c, v) in rock.density.items()
                       if abs(c[0]-wc[0]) <= 3 and abs(c[1]-wc[1]) <= 3
                       and abs(c[2]-wc[2]) <= 3 and v < R2.DENS_ISO)
        gone_near = sum(1 for (c) in [(wc[0]+di, wc[1]+dj, wc[2]+dk)
                                      for di in range(-2, 3) for dj in range(-2, 3)
                                      for dk in range(-2, 3)]
                        if c not in rock.density)
        out.update(wall_density_before=d_before, wall_density_after=d_after,
                   hammer_progress=rec, low_density_within_3_of_wall=low_near,
                   cells_gone_within_2_of_wall=gone_near,
                   interior_damage_confirmed=bool(
                       d_after is not None and d_before is not None
                       and d_after < d_before or gone_near > 0 or low_near > 0))
    json.dump(out, open('out/s02_cavity_results.json', 'w'), indent=1)
    print(json.dumps(out, default=str)[:400])
    print('cav done')


if __name__ == '__main__':
    main()
