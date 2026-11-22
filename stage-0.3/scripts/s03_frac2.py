"""DENT Stage 0.3 — FRAC2: natural fracture scenarios 1-8 (grain effect).

Questions:
  Q1. Do cracks initiate from ordinary accumulated taps on the real rock? (0.2: yes)
  Q2. Can a MULTI-CELL fragment detach NATURALLY (no prescribed cuts)?
      Stage 0.2: no (all fragments 1 cell). Hypothesis: with a grain-structured
      bond lattice (inter-granular bonds weaker), cracks follow grain
      boundaries and can close loops -> multi-cell fragments.
  Q3. Scenario-dependence of crack initiation and propagation (8 scenarios).

Scenarios (all taps from OUTSIDE along deterministic jittered ray fans):
  1 flat/broad face      2 corner            3 exposed edge
  4 narrow waist         5 adjacent craters  6 around weakened region
  7 widely distributed   8 concentrated then distributed (combination)

For each scenario x {grain, control}: first-sever tap (initiation), severed
bonds, crack clusters, fragment count/volumes (components at 25/50/75/100%),
mass retained/removed, seconds.

Output: out/s03_frac2_results.json
"""
import json, math, os, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3

N_TAPS = 6000


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def outward_normal(rock, c):
    w = []
    for dx, dy, dz in R3._NEIGH6:
        if (c[0]+dx, c[1]+dy, c[2]+dz) not in rock.density:
            w.append((dx, dy, dz))
    if not w:
        return (0.0, 0.0, 1.0)
    n = [sum(v[i] for v in w) for i in range(3)]
    ln = math.sqrt(sum(x*x for x in n)) or 1.0
    return tuple(x/ln for x in n)


def solid_neighbours(rock, c):
    return sum(1 for dx, dy, dz in R3._NEIGH6
               if (c[0]+dx, c[1]+dy, c[2]+dz) in rock.density)


def centre(rock, c):
    return tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))


def find_landmarks(rock):
    """flat cells, corners, edges, narrowest waist (axis x runs)."""
    flat, corner, edge = [], [], []
    for c in rock.density:
        n = solid_neighbours(rock, c)
        if n == 5:
            flat.append(c)
        elif n <= 2:
            corner.append(c)
        elif n == 3:
            edge.append(c)
    # narrowest waist: shortest solid runs along x
    L = rock.L
    runs = []
    for j in range(L):
        for k in range(L):
            run = []
            for i in range(L):
                if (i, j, k) in rock.density:
                    run.append(i)
                elif run:
                    if 2 <= len(run) <= 7:
                        runs.append((run, j, k))
                    run = []
            if run and 2 <= len(run) <= 7:
                runs.append((run, j, k))
    waist = None
    if runs:
        c0 = L // 2
        runs.sort(key=lambda rk: abs(rk[0][len(rk[0])//2] - c0))
        r, j, k = runs[0]
        waist = (r[len(r)//2], j, k)
    return dict(flat=flat, corner=corner, edge=edge, waist=waist)


def ray_patch(rnd, tgt, normal, n=18, jitter=0.05):
    """n rays converging on tgt from outside; jitter target not direction."""
    rays = []
    for q in range(n):
        jt = tuple(tgt[i] + rnd.uniform(-jitter, jitter) for i in range(3))
        vd = tuple(-normal[i] + rnd.uniform(-0.15, 0.15) for i in range(3))
        rays.append((jt, vd))
    return rays


def scenario_rays(rock, lm, scen, seed):
    rnd = random.Random(seed)
    if scen == 1:
        c = max(lm["flat"], key=lambda c: c[1])
        return ray_patch(rnd, centre(rock, c), (0.0, 1.0, 0.0))
    if scen == 2:
        c = min(lm["corner"], key=lambda c: sum(abs(x - rock.L/2) for x in c))
        n = outward_normal(rock, c)
        return ray_patch(rnd, centre(rock, c), n, n=24, jitter=0.03)
    if scen == 3:
        eds = lm["edge"]
        c = eds[len(eds)//2]
        n = outward_normal(rock, c)
        return ray_patch(rnd, centre(rock, c), n, n=20)
    if scen == 4:
        c = lm["waist"]
        n = outward_normal(rock, c)
        return ray_patch(rnd, centre(rock, c), n, n=20)
    if scen == 5:
        c = max(lm["flat"], key=lambda c: c[1])
        p0 = centre(rock, c)
        offs = [(0.10, 0, 0.05), (-0.10, 0, 0.05), (0, 0.0, -0.10)]
        rays = []
        for off in offs:
            tgt = tuple(p0[i] + off[i] for i in range(3))
            rays += ray_patch(rnd, tgt, (0.0, 1.0, 0.0), n=12)
        return rays
    if scen in (6, 8):
        c = max(lm["flat"], key=lambda c: c[1])
        return ray_patch(rnd, centre(rock, c), (0.0, 1.0, 0.0), n=12)  # phase 1
    raise ValueError(scen)


def crack_clusters(rock):
    """Clusters of cells adjacent to severed bonds (proxy used in 0.2)."""
    cells = set()
    for b in rock.severed:
        va, vb = b >> 24, b & 0xFFFFFF
        cells.add(R3.vunkey(va, rock.L)); cells.add(R3.vunkey(vb, rock.L))
    seen = set(); out = []
    for s in cells:
        if s in seen:
            continue
        comp = {s}; seen.add(s); st = [s]
        while st:
            c = st.pop()
            for dx, dy, dz in R3._NEIGH6:
                n = (c[0]+dx, c[1]+dy, c[2]+dz)
                if n in cells and n not in seen:
                    seen.add(n); comp.add(n); st.append(n)
        out.append(len(comp))
    out.sort(reverse=True)
    return len(out), out[:4]


def run_scenario(scen, grain, taps=N_TAPS, seed=1234):
    verts, tris = gen_rock2(48)
    rock = R3.RockDensity(verts, tris, lattice=72, grain=grain)
    cells0 = len(rock.density)
    lm = find_landmarks(rock)
    rays = scenario_rays(rock, lm, scen, seed) if scen != 7 else []
    rnd = random.Random(seed + 999)
    events = dict(first_sev=None, first_frag_multi=None)
    checks = set()
    acc = 0
    t0 = time.time()
    for q in range(taps):
        if scen == 7 or (scen == 8 and q >= 2000):
            tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6))
            o, d = ray_into(rock, tgt, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1)))
        else:
            tgt, vd = rays[q % len(rays)]
            o, d = ray_into(rock, tgt, vd)
        r = rock.tap_ray(o, d)
        if r["ok"]:
            acc += 1
        if events["first_sev"] is None and rock.s["sev_total"] > 0:
            events["first_sev"] = acc
        frac = (acc / taps)
        for cf in (0.25, 0.50, 0.75, 1.0):
            if frac >= cf and cf not in checks:
                checks.add(cf)
                comps = rock.components()
                frags = sorted((len(x) for x in comps[1:]), reverse=True)
                if frags and max(frags) > 1 and events["first_frag_multi"] is None:
                    events["first_frag_multi"] = acc
        if not rock.density:
            break
    comps = rock.components()
    frags = sorted((len(x) for x in comps[1:]), reverse=True)
    nclust, top = crack_clusters(rock)
    return dict(scenario=f"S{scen}", name=S_NAMES[scen-1], grain=grain, taps=taps, accepted=acc,
                seeded=taps - acc, first_sev=events["first_sev"],
                first_multi_frag=events["first_frag_multi"],
                frag_count=len(frags), frag_top=frags[:8],
                multi_frag_count=sum(1 for f in frags if f > 1),
                frag_cells=sum(frags),
                sev_total=rock.s["sev_total"],
                crack_clusters=nclust, crack_top=top,
                crumbles=rock.s["crumbles"], cells_left=len(rock.density),
                cells0=cells0, seconds=round(time.time() - t0, 1),
                hash=rock.hash_state())


S_NAMES = ["broad_face", "corner", "edge", "narrow_waist", "adjacent_craters",
           "around_weakened", "distributed", "concent_then_distributed"]


def main():
    out = []
    scen_list = sys.argv[1:] or ["1", "2", "3", "4", "5", "6", "7", "8"]
    for s in scen_list:
        grains = (True, False) if os.environ.get("GRAINCTL", "1") == "1" else (True,)
        for grain in grains:
            try:
                r = run_scenario(int(s), grain)
                r["name"] = S_NAMES[int(s)-1]
            except Exception as e:
                r = dict(scenario=f"S{s}", grain=grain, error=repr(e), name=S_NAMES[int(s)-1])
            out.append(r)
            print(json.dumps(r), flush=True)
            json.dump(out, open("out/s03_frac2_results.json", "w"), indent=1)
    print("frac2 done", flush=True)


if __name__ == "__main__":
    main()
