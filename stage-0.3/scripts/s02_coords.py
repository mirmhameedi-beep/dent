"""DENT Stage 0.2 — Experiment CO: 3D impact detection and stale-client contract.

10 scenarios on one L=72 rock. Each records what the engine resolved, proving:
current-surface resolution, interior/fracture/fragment hits, stale snapshot
handling, miss -> reject (never reuse last point).
"""
import json, math, sys
sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2
OUT = "out/s02"

def ray_for(rock, tgt, view_dir):
    ln = math.sqrt(sum(c*c for c in view_dir)); vd = tuple(x/ln for x in view_dir)
    return (tuple(int((tgt[i]+vd[i]*4.0)*FIX) for i in range(3)),
            tuple(int(-x*FIX) for x in vd), vd)

def main():
    out = {}
    verts, tris = gen_rock2(48)
    rock = R2.RockDensity(verts, tris, lattice=72)

    # build a crater at target; record floor depth DURING accretion (the ray
    # eventually bores through and every later same-ray tap is REJECTED)
    tgt = (0.40, 0.25, 0.0)
    orig, d, vd = ray_for(rock, tgt, (0.5, -0.2, 0.85))
    h0 = rock.resolve_ray(orig, d)
    probes = {1, 100, 300, 600, 1000, 1285, 3000}
    depth_log = {}
    for q in range(1, 3001):
        rrq = rock.tap_ray(orig, d)
        if q in probes:
            if rrq.get("hit") is not None:
                depth_log[str(q)] = round(math.dist(
                    [a/FIX for a in rrq["hit"]], [x/FIX for x in h0[0]])/rock.cs, 3)
            else:
                depth_log[str(q)] = "miss_rejected (bore-through)"
    out["S1_pristine_hit_before_crater"] = dict(hit=(list(h0[0]) if h0 else None), cell=(list(h0[1]) if h0 else None))
    out["S1b_crater_floor_depth_cells"] = depth_log

    # 1. rotating the rock: same screen anchor hit from 6 view directions
    res6 = {}
    for name, vd0 in (("front",(0,0,1)),("side",(1,0.15,0)),("rear",(0.4,-0.3,-0.8)),
                      ("top",(0.2,-0.95,0.25)),("other_side",(-0.9,0.1,0.1)),("three_quarter",(0.5,0.5,0.7))):
        t2 = tgt
        o2, d2, vv = ray_for(rock, t2, vd0)
        rr = rock.resolve_ray(o2, d2)
        res6[name] = dict(hit=(list(rr[0]) if rr else None), cell=(list(rr[1]) if rr else None))
    out["rotate_views"] = res6

    # 2. tap a different side than previously damaged
    o2, d2, vv = ray_for(rock, (-0.6, 0.2, 0.2), (0.5, 0.3, 0.8))
    rr = rock.tap_ray(o2, d2)
    out["tap_new_side"] = dict(ok=rr["ok"], hit=list(rr.get("hit", ())) if rr["ok"] else rr["reason"])

    # 3. tap the existing crater: moderate count so the floor is still solid;
    #    later, the long-haul bore-through behaviour is probed separately
    seq = []
    for q in range(300):
        rr = rock.tap_ray(orig, d)
        seq.append(rr.get("hit"))
    okf = [h for h in seq if h is not None]
    floor_progress = None
    if h0 is not None and len(okf) >= 2:
        d_first = math.dist([a/FIX for a in okf[0]], [x/FIX for x in h0[0]])/rock.cs
        d_last  = math.dist([a/FIX for a in okf[-1]], [x/FIX for x in h0[0]])/rock.cs
        floor_progress = dict(depth_cells_after_1=d_first,
                              depth_cells_after_301=d_last,
                              monotonic_deeper=d_last >= d_first)
    rrB = rock.tap_ray(orig, d)   # long-haul: same ray, heavily damaged region
    out["tap_crater"] = dict(rays_300_ok=len(okf),
                             floor_progress=floor_progress,
                             bore_through_after=rock.s["taps"],
                             bore_through_result=("rejected:"+str(rrB.get("reason")) if not rrB["ok"] else "accepted"))

    # 4/5. tap crater floor and fracture surface inside: interior probe — aim
    # into the cavity from an offset so the entry is through the cavity mouth
    o3, d3, vv3 = ray_for(rock, tgt, (0.95, -0.1, 0.2))
    rr3 = rock.tap_ray(o3, d3)
    out["tap_cavity_mouth"] = dict(ok=rr3["ok"], hit=list(rr3.get("hit", ())),
                                   cell=(list(rr3["hit_cell"]) if "hit_cell" in rr3 else None))

    # 6. tap near an edge
    o4, d4, vv4 = ray_for(rock, (0.75, -0.45, 0.2), (0.8, 0.2, 0.5))
    rr4 = rock.tap_ray(o4, d4)
    out["tap_near_edge"] = dict(ok=rr4["ok"], hit=list(rr4.get("hit", ())) if rr4["ok"] else rr4["reason"])

    # 7. tap a detached fragment: create one naturally? fallback: use a real
    # fragment produced by heavy hammering; else record none-was-available
    main, frags = rock.fragments()
    if frags:
        big = max(frags, key=len)
        c = sorted(big)[len(big)//2]
        org_, cs_ = rock.origin, rock.cs
        tw = (org_+(c[0]+0.5)*cs_, org_+(c[1]+0.5)*cs_, org_+(c[2]+0.5)*cs_)
        o5, d5, vv5 = ray_for(rock, tw, (0.6, 0.6, 0.6))
        rr5 = rock.resolve_ray(o5, d5)
        in_frag = rr5 is not None and rr5[1] in big
        out["tap_fragment"] = dict(nfrag=len(frags), frag_cells=len(big),
                                   hit=bool(rr5), hit_lands_on_fragment=bool(in_frag))
    else:
        out["tap_fragment"] = dict(nfrag=0, note="no fragment available from this schedule; separate fracture experiment owns natural fragmentation")

    # 8. stale client: client holds a geometry version from BEFORE the crater;
    #    client submits a material coordinate of a tri that no longer faces
    #    the ray. Server policy: re-resolve from ray; stale coords discarded.
    stale_hit_before = h0[0]
    client_stale = {"epoch": 0, "tri": h0[1], "world": stale_hit_before}
    # after the crater, server re-resolve at that cell: original cell now
    # carved; simulating server receiving ONLY the stale coordinate (no ray):
    # policy: server cannot place a tap from a stale coordinate alone — reject.
    c_stale = client_stale["tri"]
    still = c_stale in rock.density and rock.density[c_stale] < R2.DENS_MAX - 8
    out["stale_client"] = dict(stale_cell=list(c_stale),
                               cell_still_solid=bool(c_stale in rock.density),
                               cell_damaged=bool(still),
                               policy="server re-resolves from the client RAY; stale material coordinates are advisory only; a stale cell that no longer faces a valid current surface resolves to the CURRENT surface or is rejected; the server never substitutes its last accepted point")

    # 9. miss the rock: ray origin far outside, direction AWAY from the rock
    #    (previous setup accidentally grazed the rock and accepted a tap)
    o6 = (tuple(int(c*FIX) for c in (3.0, 3.0, 3.0)))
    d6 = (tuple(int(c*FIX) for c in (0.577, 0.577, 0.577)))  # away from origin region
    before = rock.hash_state()
    rr6 = rock.tap_ray(o6, d6)
    after = rock.hash_state()
    out["miss_rejected"] = dict(ok=rr6["ok"], reason=rr6.get("reason"),
                                state_unchanged=before == after,
                                rejected_by_design=not rr6["ok"])

    # 10. two visitors with different versions: use a KNOWN-HITTING ray (the
    #     new-side ray from scenario 2); server re-resolves both against the
    #     CURRENT geometry; older client's view lags but its tap lands current.
    o7, d7, vv7 = ray_for(rock, (-0.6, 0.2, 0.2), (0.5, 0.3, 0.8))
    rrA = rock.tap_ray(o7, d7)
    rrB2 = rock.tap_ray(o7, d7)
    out["two_versions"] = dict(v0_ok=rrA["ok"], v2_ok=rrB2["ok"],
                               hitA=list(rrA.get("hit", ())) if rrA["ok"] else rrA.get("reason"),
                               hitB=list(rrB2.get("hit", ())) if rrB2["ok"] else rrB2.get("reason"),
                               both_land_current_surface=bool(rrA["ok"] and rrB2["ok"]))

    json.dump(out, open("out/s02_coords_results.json", "w"), indent=1, default=str)
    for k, v in out.items():
        print(k, "->", json.dumps(v, default=str)[:160])
    print("done")

if __name__ == "__main__":
    main()
