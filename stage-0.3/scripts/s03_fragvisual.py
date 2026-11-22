"""DENT Stage 0.3 — natural-fragment VISUAL evidence: run the S4 narrow-waist
scenario (grain), save exact states, render the developing crack + the detached
multi-cell fragment (MT extraction renders fragments as separate surfaces)."""
import json, math, os, random, sys, time
sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3
import s03_frac2 as F
import s02_mt as MT
import s02_render as RD

OUT = "out/s03_states"
os.makedirs(OUT, exist_ok=True)
CHECKS = (0.25, 0.50, 0.75, 1.0)
names = {0.25: "FRAG25", 0.50: "FRAG50", 0.75: "FRAG75", 1.0: "FRAG100"}

verts, tris = gen_rock2(48)
rock = R3.RockDensity(verts, tris, lattice=72, grain=True)
lm = F.find_landmarks(rock)
rays = F.scenario_rays(rock, lm, 4, 1234)
rnd = random.Random(1234 + 999)
N_TAPS = 6000
acc = 0
done = set()
for q in range(N_TAPS):
    tgt, vd = rays[q % len(rays)]
    o, d = F.ray_into(rock, tgt, vd)
    r = rock.tap_ray(o, d)
    if r["ok"]:
        acc += 1
    frac = acc / N_TAPS
    for cf in CHECKS:
        if frac >= cf and cf not in done:
            done.add(cf)
            comps = rock.components()
            comps.sort(key=len, reverse=True)
            frags = sorted((len(x) for x in comps[1:]), reverse=True)
            mv, mn, mt = MT.extract_mt(rock)
            wv = [(round(x*65536), round(y*65536), round(z*65536)) for x, y, z in mv]
            # find the fragment+crack region: bbox of cells in all-but-largest
            # components -> close-up target (world coords)
            frags_cells = [cc for comp in comps[1:] for cc in comp] if len(comps) > 1 else []
            tgt = None
            if frags_cells:
                cx = sum(rock.origin + (cc[0]+0.5)*rock.cs for cc in frags_cells)/len(frags_cells)
                cy = sum(rock.origin + (cc[1]+0.5)*rock.cs for cc in frags_cells)/len(frags_cells)
                cz = sum(rock.origin + (cc[2]+0.5)*rock.cs for cc in frags_cells)/len(frags_cells)
                tgt = (cx, cy, cz)
            RD.render_mesh(wv, mt, f"{OUT}/{names[cf]}_front.png",
                           view=(0.35, -0.25, 0.9), zoom=1.0)
            if tgt:
                RD.render_mesh(wv, mt, f"{OUT}/{names[cf]}_close.png",
                               view=(0.35, -0.25, 0.9), zoom=8.0, target=tgt, size=460)
            json.dump(dict(check=cf, accepted=acc, components=len(comps),
                           largest=len(comps[0]), frags_top=frags[:6],
                           sev=rock.s["sev_total"], crumbles=rock.s["crumbles"]),
                      open(f"out/s03_fragvisual_{names[cf]}.json", "w"), indent=1)
            print(cf, acc, "comps", len(comps), "largest", len(comps[0]),
                  "frags", frags[:6], flush=True)
print("fragvisual done; accepted:", acc)
