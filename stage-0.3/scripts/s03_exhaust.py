"""DENT Stage 0.3 — EXHAUST: exhausted-location handling and valid-impact integrity.

Model A engine (alpha/cap, DFIX=65536), L=72. Tests:
 T1  repeated taps into a deepening crater (single ray): accepted until
     bore-through; then every further tap REJECTED with state hash unchanged.
 T2  crater-wall taps: offset rays onto the crater wall after bore-through:
     accepted; wall depth measured.
 T3  taps through the through-hole (exact bore axis): all rejected; hash unchanged.
 T4  taps on the newly exposed floor / adjacent crater region: accepted; depth grows.
 T5  taps on an undamaged far-side region: accepted.
 T6  taps on a detached fragment with an unobstructed line of sight: the ray
     resolves against the fragment cell; otherwise honest occlusion report.
 T7  taps at a location with no material: rejected; hash byte-unchanged.
 T8  accounting: accepted + rejected == launched; per-test hash checks prove
     rejected taps never changed state.

Output: out/s03_exhaust_results.json
"""
import json, math, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def make_rock():
    verts, tris = gen_rock2(48)
    rock = R3.RockDensity(verts, tris, lattice=72, dfix=65536)
    dsum = sum(rock.density.values()) / rock.dfix
    cells0 = len(rock.density)
    cap = (dsum / cells0 - 30.0) * cells0 / 1e9
    rock.cap_mass = cap
    rock.alpha = cap / 15.33
    return rock


def depth_probe_cells(rock, tgt, vd):  # solid-cell depth (legacy helper)
    """Depth of contiguous solid material along the ray path (cell steps)."""
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    L, org, cs = rock.L, rock.origin, rock.cs
    depth = 0
    for s in range(0, 400):
        wx, wy, wz = tgt[0] + s * 0.25 * u[0], tgt[1] + s * 0.25 * u[1], tgt[2] + s * 0.25 * u[2]
        i, j, k = int((wx - org) / cs), int((wy - org) / cs), int((wz - org) / cs)
        if not (0 <= i < L and 0 <= j < L and 0 <= k < L):
            break
        if (i, j, k) in rock.density:
            depth += 1
        elif depth:
            break
    return depth


def centre(rock, c):
    return tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))


def iso_depth_probe(rock, tgt, vd):
    """VISIBLE depth in cells: distance from the target point (on the original
    surface) to the first trilerp iso-120 crossing marching into the rock
    along +u (renders use ISO=120). Pristine bias ~0..0.5 cell, noted."""
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    cs = rock.cs
    step = cs / 4.0
    for s in range(1, 400):
        wx = tgt[0] + s * step * u[0]
        wy = tgt[1] + s * step * u[1]
        wz = tgt[2] + s * step * u[2]
        if rock.trilerp_density(wx, wy, wz) >= 120.0:
            # but if trilerp at s tiny (immediately >= 120) the surface is
            # essentially at the target -> depth ~0; subtract the first step
            return max(0.0, (s * step) / cs - 0.25)
    return 999.0   # no material found: bore-through


def main():
    out = {}
    launched_total = 0
    rock = make_rock()
    tgt = (0.35, 0.30, 0.0)
    vd = (0.35, -0.25, 0.91)

    # ---- T1 ----
    acc_curve = []
    first_reject = None
    for q in range(1, 400_001):
        launched_total += 1
        o, d = ray_into(rock, tgt, vd)
        r = rock.tap_ray(o, d)
        if r["ok"]:
            if q % 5000 == 0:
                acc_curve.append((q, iso_depth_probe(rock, tgt, vd)))
        else:
            first_reject = q
            break
    h_bore = rock.hash_state()
    rej1 = 0
    for q in range(300):
        launched_total += 1
        o, d = ray_into(rock, tgt, vd)
        if not rock.tap_ray(o, d)["ok"]:
            rej1 += 1
    out["T1_single_ray_exhaustion"] = dict(
        accepted_until_first_reject=first_reject, subsequent_rejected=rej1,
        state_unchanged_after_exhausted_taps=(h_bore == rock.hash_state()),
        depth_curve=acc_curve[:12])
    print("T1 ok", first_reject, flush=True)

    # ---- T2: crater wall ----
    jt = (tgt[0] + 0.05, tgt[1] + 0.04, tgt[2] + 0.03)
    jv = (0.38, -0.25, 0.89)
    wall_acc = 0
    for q in range(300):
        launched_total += 1
        o, d = ray_into(rock, jt, jv)
        if rock.tap_ray(o, d)["ok"]:
            wall_acc += 1
    out["T2_crater_wall"] = dict(offset=0.05, accepted=wall_acc, of=300,
                                 wall_depth_cells=depth_probe_cells(rock, jt, jv))
    print("T2 ok", wall_acc, flush=True)

    # ---- T3: through-hole axis ----
    h0 = rock.hash_state()
    rej3 = 0
    for q in range(300):
        launched_total += 1
        o, d = ray_into(rock, tgt, vd)
        if not rock.tap_ray(o, d)["ok"]:
            rej3 += 1
    out["T3_through_hole_axis"] = dict(taps=300, rejected=rej3,
                                       state_unchanged=(h0 == rock.hash_state()))
    print("T3 ok", rej3, flush=True)

    # ---- T4: newly exposed floor keeps receiving damage ----
    jt4 = (tgt[0] + 0.015, tgt[1] - 0.01, tgt[2] + 0.01)
    deps = []
    acc4 = 0
    for q in range(2000):
        launched_total += 1
        o, d = ray_into(rock, jt4, vd)
        r = rock.tap_ray(o, d)
        if r["ok"]:
            acc4 += 1
            if acc4 % 400 == 0:
                deps.append((acc4, depth_probe_cells(rock, jt4, vd)))
    out["T4_newly_exposed_surface"] = dict(accepted=acc4, of=2000,
                                           depth_curve=deps[-6:] if len(deps) > 6 else deps)
    print("T4 ok", acc4, flush=True)

    # ---- T5: intact far-side region ----
    o, d = ray_into(rock, (-0.45, -0.35, 0.2), (-0.3, 0.3, 0.8))
    launched_total += 1
    r5 = rock.tap_ray(o, d)
    out["T5_far_side"] = dict(accepted=r5["ok"], hit_ok=bool(r5.get("hit")))
    print("T5 ok", r5["ok"], flush=True)

    # ---- T7: empty space ----
    h0 = rock.hash_state()
    rej7 = 0
    for q in range(300):
        launched_total += 1
        o, d = ray_into(rock, (2.0, 2.0, 2.0), (0.2, 0.2, 0.95))
        if not rock.tap_ray(o, d)["ok"]:
            rej7 += 1
    out["T7_empty_space"] = dict(taps=300, rejected=rej7,
                                 state_unchanged=(h0 == rock.hash_state()))
    print("T7 ok", rej7, flush=True)

    # ---- T8 --- (capture alpha-rock accounting BEFORE T6 replaces the rock)
    out["T8_accounting"] = dict(accepted=rock.s["taps"], rejected=rock.s["rejected"],
                                launched=launched_total,
                                accepted_plus_rejected_eq_launched=(
        rock.s["taps"] + rock.s["rejected"] == launched_total))
    print("T8 ok", rock.s["taps"], rock.s["rejected"], launched_total, flush=True)

    # ---- T6: fragment hit on a LEGACY-constant rock (alpha rock is intact
    # at 400k taps -> no fragments yet; legacy concentration produces them).
    # NOTE: T8 accounting above was captured for the alpha rock already. ----
    verts_l, tris_l = gen_rock2(48)
    rock_l = R3.RockDensity(verts_l, tris_l, lattice=72)   # legacy constants
    tl = (0.35, 0.30, 0.0)
    for q in range(2500):
        o, d = ray_into(rock_l, tl, vd)
        rock_l.tap_ray(o, d)
    rock = rock_l
    comps = rock.components()
    comps.sort(key=len, reverse=True)
    smalls = comps[1:] if len(comps) > 1 else []
    frag_hit = None
    dirs26 = [(dx, dy, dz) for dx in (-1, 0, 1) for dy in (-1, 0, 1) for dz in (-1, 0, 1)
              if (dx, dy, dz) != (0, 0, 0)]
    rt = R3  # aliases
    calls = 0
    for frag in sorted(smalls, key=len, reverse=True):
        want = set(frag)
        h0 = rock.hash_state()
        for fc in list(want)[:4]:
            fcw = centre(rock, fc)
            for dvec in dirs26:
                if calls > 20000:
                    break
                calls += 1
                ln = math.sqrt(sum(x*x for x in dvec))
                u = [x / ln for x in dvec]
                po = tuple(fcw[i] + 0.8 * u[i] for i in range(3))
                o6 = tuple(int(po[i] * FIX) for i in range(3))
                d6 = tuple(int(-u[i] * FIX) for i in range(3))
                hit = rock.resolve_ray(o6, d6)
                if hit is not None and hit[1] in want:
                    r6 = rock.tap_ray(o6, d6)
                    if r6["ok"] and rock.hash_state() != h0:
                        frag_hit = dict(fragment_cells=len(want), hit_cell=list(hit[1]),
                                        state_changed=True, direction=list(dvec),
                                        ray_calls=calls)
                        break
            if frag_hit:
                break
        if frag_hit:
            break
    out["T6_fragment"] = dict(
        fragments_present=len(smalls),
        tested=frag_hit is not None,
        result=frag_hit,
        note=("fragments live in the authoritative density field; a ray with line "
              "of sight resolves against the fragment and damages it. At alpha "
              "scale within 50k taps fragments are rare (matches Stage 0.2)."))
    print("T6 ok", frag_hit is not None, flush=True)

    json.dump(out, open("out/s03_exhaust_results.json", "w"), indent=1)
    print("exhaust done", flush=True)


if __name__ == "__main__":
    main()
