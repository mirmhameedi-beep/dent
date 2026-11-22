"""DENT Stage 0.2 — Experiment FR: natural fracture and crack propagation.

Six scenarios on L=72 rocks (same pristine rock each time), NO prescribed cuts:
  FR1 centre of a broad face
  FR2 along a natural edge (high-curvature boundary band)
  FR3 near the narrow crevice floor (thin section)
  FR4 five neighbouring craters
  FR5 widely distributed
  FR6 pre-weakened region then hammered at the crater root
Each: taps -> severed-bond clusters (crack evidence), fragments, masses.
"""
import json, math, random, sys, time
sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2, s02_mt as MT, s02_render as RD

OUT = "out/s02"
L = 72


def make_rock():
    verts, tris = gen_rock2(48)
    return R2.RockDensity(verts, tris, lattice=L)


def ray_for_target(rock, tgt_world, view_dir):
    ln = math.sqrt(sum(c*c for c in view_dir))
    vd = tuple(x/ln for x in view_dir)
    orig = tuple(int((tgt_world[i] + vd[i]*4.0)*FIX) for i in range(3))
    d = tuple(int(-x*FIX) for x in vd)
    return orig, d, vd


def hammer(rock, orig, d, n):
    acc = rej = 0
    for q in range(n):
        rr = rock.tap_ray(orig, d)
        if rr["ok"]:
            acc += 1
        else:
            rej += 1
    return acc, rej


def edge_band_cells(rock, kmin=3):
    """Boundary cells whose surface curvature looks edge-like (>=3 of 8
    horizontal neighbours missing) — crude but deterministic edge finder."""
    edges = []
    for c in rock.density:
        i, j, k = c
        hor = sum(1 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)) if (i+dx, j+dy, k) in rock.density)
        if 1 <= hor <= 3:
            edges.append(c)
    return edges


def severed_clusters(rock):
    """Clusters of severed bonds sharing cells — crack map."""
    import collections
    L = rock.L
    cells_of = collections.defaultdict(list)
    for b in rock.severed:
        va, vb = b >> 24, b & 0xFFFFFF
        cells_of[va].append(vb); cells_of[vb].append(va)
    seen = set(); clusters = []
    for v in list(cells_of):
        if v in seen: continue
        stack=[v]; comp=[v]; seen.add(v)
        while stack:
            x = stack.pop()
            for y in cells_of[x]:
                if y not in seen:
                    seen.add(y); comp.append(y); stack.append(y)
        clusters.append(comp)
    clusters.sort(key=len, reverse=True)
    return clusters


def snapshot_render(rock, tag, target, vd):
    mv, mn, mt = MT.extract_mt(rock)
    wv = [(round(x*FIX), round(y*FIX), round(z*FIX)) for x, y, z in mv]
    RD.render_mesh(wv, mt, f"{OUT}/{tag}_34.png", view=(0.62, 0.5, 0.7), size=420)
    RD.render_mesh(wv, mt, f"{OUT}/{tag}_close.png", view=vd, zoom=3.0,
                   target=target, size=420)


def scenario(name, rock, plan, render_target, vd):
    t0 = time.perf_counter()
    total_accepted = 0
    for (label, orig, d, n) in plan:
        acc, rej = hammer(rock, orig, d, n)
        total_accepted += acc
    main, frags = rock.fragments()
    sizes = sorted((len(x) for x in frags), reverse=True)
    clusters = severed_clusters(rock)
    cl_sizes = sorted((len(c) for c in clusters), reverse=True)
    row = dict(name=name, accepted=total_accepted,
               crumbles=rock.s["crumbles"], severed=rock.s["sev_total"],
               nfrag=len(frags), frag_top=sizes[:8],
               crack_clusters=len(clusters), crack_top=cl_sizes[:8],
               cells=len(rock.density), seconds=round(time.perf_counter()-t0, 1))
    print(name, row, flush=True)
    snapshot_render(rock, name, render_target, vd)
    return row


def main():
    out = []
    t00 = time.perf_counter()

    # FR1 centre of broad face (same anchor as lifecycle but at L=72)
    rock = make_rock()
    tgt = (0.35, 0.30, 0.0)
    orig, d, vd = ray_for_target(rock, tgt, (0.35, -0.25, 0.91))
    out.append(scenario("FR1_centre_face", rock, [("main", orig, d, 40000)], tgt, vd))

    # FR2 along a natural edge: find edge-band cells, hammer a line of 12 of them
    rock = make_rock()
    edges = edge_band_cells(rock)
    # choose a connected run: sort by coordinate, take consecutive cells near the +x limb
    edges.sort(key=lambda c: (c[2], abs(c[0]), abs(c[1])))
    run = []
    for c in edges:
        if c[0] > 40 and len(run) < 14:
            run.append(c)
    print("FR2 edge cells:", run[:3], "n=%d" % len(run), flush=True)
    plan = []
    org = rock.origin; cs = rock.cs
    for (i, j, k) in run:
        tw = (org + (i+0.5)*cs, org + (j+0.5)*cs, org + (k+0.5)*cs)
        rd = (1.0, 0.15, 0.1)
        o, d2, vv = ray_for_target(rock, tw, rd)
        plan.append((f"edge_{i}_{j}_{k}", o, d2, 1200))
    cw = (org + (run[0][0]+0.5)*cs, org + (run[0][1]+0.5)*cs, org + (run[0][2]+0.5)*cs) if run else (0,0,0)
    out.append(scenario("FR2_edge_line", rock, plan, cw, (1.0, 0.15, 0.1)))

    # FR3 crevice floor (narrow section) — find cells at the bottom of the crevice:
    # solid cells with high emptiness inside the crevice plane band y~0.3x
    rock = make_rock()
    cand = []
    for (i, j, k) in rock.density:
        wi, wj, wk = org+(i+0.5)*cs, org+(j+0.5)*cs, org+(k+0.5)*cs
        # crevice plane: y = 0.3*x  (normal (-0.287, 0.958, 0))
        dist_plane = abs(wj - 0.3*wi)/math.sqrt(1.09)
        if dist_plane < 0.09 and abs(WX:=wi) < 0.5 and abs(wk) < 0.55:
            n_empty = sum(1 for dx, dy, dz in R2._NEIGH6 if (i+dx, j+dy, k+dz) not in rock.density)
            if n_empty >= 1:
                cand.append((dist_plane, i, j, k))
    cand.sort()
    run = [c[1:] for c in cand[:10]]
    print("FR3 crevice cells:", run[:3], "n=%d" % len(run), flush=True)
    plan = []
    for (i, j, k) in run:
        tw = (org+(i+0.5)*cs, org+(j+0.5)*cs, org+(k+0.5)*cs)
        o, d2, vv = ray_for_target(rock, tw, (-0.287, 0.958, 0.0))
        plan.append((f"crev_{i}_{j}_{k}", o, d2, 1500))
    cw = (org+(run[0][0]+0.5)*cs, org+(run[0][1]+0.5)*cs, org+(run[0][2]+0.5)*cs) if run else (0,0,0)
    out.append(scenario("FR3_crevice_floor", rock, plan, cw, (0.62, 0.5, 0.7)))

    # FR4 neighbouring craters
    rock = make_rock()
    sites = [(-0.35, 0.15, 0.0), (-0.42, 0.26, 0.12), (-0.28, 0.30, -0.10),
             (-0.5, 0.0, 0.2), (-0.36, -0.02, 0.34)]
    plan = []
    for s in sites:
        o, d2, vv = ray_for_target(rock, s, (0.5, 0.3, 0.81))
        plan.append((f"n{s}", o, d2, 5000))
    out.append(scenario("FR4_clusters", rock, plan, sites[0], (0.5, 0.3, 0.81)))

    # FR5 widely distributed
    rock = make_rock()
    rng = random.Random(4242)
    boundary = sorted(rock.density)
    plan = []
    for q in range(40):
        c = boundary[rng.randrange(len(boundary))]
        tw = (org+(c[0]+0.5)*cs, org+(c[1]+0.5)*cs, org+(c[2]+0.5)*cs)
        rd = (rng.uniform(-1,1), rng.uniform(-1,1), rng.uniform(0.2,1.0))
        o, d2, vv = ray_for_target(rock, tw, rd)
        plan.append((f"w{q}", o, d2, 500))
    out.append(scenario("FR5_distributed", rock, plan, (0,0,0), (0.62, 0.5, 0.7)))

    # FR6 pre-weaken then hammer the root
    rock = make_rock()
    tgt = (0.35, 0.30, 0.0)
    orig, d, vd = ray_for_target(rock, tgt, (0.35, -0.25, 0.91))
    plan1 = hammer(rock, orig, d, 12000)
    # now hammer from the side toward the weakened root
    o2, d2b, vv = ray_for_target(rock, tgt, (-0.2, 0.6, 0.8))
    plan2 = hammer(rock, o2, d2b, 12000)
    main, frags = rock.fragments()
    sizes = sorted((len(x) for x in frags), reverse=True)
    clusters = severed_clusters(rock)
    cl_sizes = sorted((len(c) for c in clusters), reverse=True)
    row = dict(name="FR6_weakened_root", accepted=24000, crumbles=rock.s["crumbles"],
               severed=rock.s["sev_total"], nfrag=len(frags), frag_top=sizes[:8],
               crack_clusters=len(clusters), crack_top=cl_sizes[:8],
               cells=len(rock.density), seconds=round(time.perf_counter()-t00,1))
    print("FR6", row, flush=True)
    snapshot_render(rock, "FR6_weakened_root", tgt, vd)
    out.append(row)

    json.dump(out, open("out/s02_fracture_results.json", "w"), indent=1, default=str)
    print("fracture done %.0fs" % (time.perf_counter()-t00))

if __name__ == "__main__":
    main()
