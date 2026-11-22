"""DENT Stage 0.2 — Experiment G2: golden fixtures for the Stage 0.2 damage rules.

Spec being fixed (contract v3 rules):
  R1 density carve:   d -= K_COMPRESS * smoothstep(1 - dist/R_IMPACT) / hardness
  R2 crumble:         density < DENS_FAIL -> cell leaves (material gone)
  R3 bond damage:     bond_dmg += K_BOND * smoothstep(1 - dist/R_BOND) / tough
                      only for bonds near a flaw (endpoint density reduced,
                      fatigue>400, or sibling bond dmg>250)
  R4 sever:           bond_dmg >= BOND_STRENGTH * tough -> severed
  R5 stress transfer: severed bond -> +SC_PROP to sibling bonds near a flaw
                      (iterative bounded worklist)
  R6 material field:  hardness/toughness/density_var from integer value noise
All integer/fixed-point under FIX=65536 world. Python generates; JS verifies.
"""
import json, sys
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 130
sys.path.insert(0, '.')

def smoothstep(t):
    if t < 0: t = 0.0
    return t*t*(3-2*t)

import common
vnoise3 = common.vnoise3

def hardness(i,j,k,seed=7):
    n = vnoise3(i*0.055, j*0.055, k*0.055, seed)
    n2 = vnoise3(i*0.25, j*0.25, k*0.25, seed+101)
    return 0.7 + 0.8*n + 0.25*n2

def toughness(i,j,k,seed=7):
    n = vnoise3(i*0.045, j*0.045, k*0.045, seed+17)
    n2 = vnoise3(i*0.25, j*0.25, k*0.25, seed+211)
    return 0.7 + 0.9*n + 0.2*n2

def gen_fixtures():
    DENS_MAX=240; DENS_FAIL=30; ISO=120
    K_COMPRESS=2.6; K_BOND=90.0; BOND_STRENGTH=1000; SC=240
    R_IMP=2.6; R_BOND=2.2
    # small standing block 4x4x6 cells, one tap at a known point
    cells = {(i,j,k): int(round(DENS_MAX * (0.92+0.08*vnoise3(i*0.25,j*0.25,k*0.25,308))))
             for i in range(4) for j in range(4) for k in range(6)}
    flds = []
    impacts = [(1.5, 1.4, 5.5)] * REPS
    cs = 1.0; org = 0.0
    sev = []
    bd = {}
    fatigue = {}
    log = []
    # fixture carries the INITIAL state; both runtimes apply REPS taps from it
    cells0 = {f"{a},{b},{c}": d for (a, b, c), d in cells.items()}
    for (wx, wy, wz) in impacts:
        ci, cj, ck = int(wx), int(wy), int(wz)
        removed = []
        for i in range(max(0,ci-3), min(4, ci+4)):
            for j in range(max(0,cj-3), min(4, cj+4)):
                for k in range(max(0,ck-3), min(6, ck+4)):
                    d0 = cells.get((i,j,k))
                    if d0 is None: continue
                    dist = ((i+0.5-wx)**2+(j+0.5-wy)**2+(k+0.5-wz)**2)**0.5
                    if dist > R_IMP: continue
                    w = smoothstep(1 - dist/R_IMP)
                    take = K_COMPRESS * w / hardness(i,j,k)
                    cells[(i,j,k)] = int(round(d0 - take)) if d0 - take >= DENS_FAIL else None
                    if d0 - take < DENS_FAIL:
                        removed.append([i,j,k]); cells.pop((i,j,k),None)
        # bond damage
        for i in range(max(0,ci-3), min(4, ci+4)):
            for j in range(max(0,cj-3), min(4, cj+4)):
                for k in range(max(0,ck-3), min(6, ck+4)):
                    c=(i,j,k)
                    if c not in cells: continue
                    dist = ((i+0.5-wx)**2+(j+0.5-wy)**2+(k+0.5-wz)**2)**0.5
                    if dist > R_BOND: continue
                    w = smoothstep(1 - dist/R_BOND)
                    fat = fatigue.get((i,j,k),0) + K_BOND*w*0.05
                    fatigue[(i,j,k)]=fat
                    for (dx,dy,dz) in ((1,0,0),(0,1,0),(0,0,1)):
                        n=(i+dx,j+dy,k+dz)
                        if n not in cells: continue
                        key=[i,j,k,dx,dy,dz]
                        bk = f"{i},{j},{k}->{n[0]},{n[1]},{n[2]}"
                        cur = bd.get(bk, 0)
                        flaw = cur>0 or (cells[c]<DENS_MAX-8) or (cells[n]<DENS_MAX-8) \
                               or fatigue.get((i,j,k),0)>400 or fatigue.get(n,0)>400
                        if not flaw: continue
                        tough=(toughness(i,j,k)+toughness(*n))*0.5
                        dmg = cur + int(K_BOND*w/tough)
                        if dmg >= BOND_STRENGTH*tough:
                            sev.append(bk); bd.pop(bk, None); log.append(f"sever {bk}")
                        else:
                            bd[bk]=dmg
                            log.append(f"bdmg {bk} {dmg}")
        log.append(f"removed {json.dumps(removed)}")
    # fatigue values are floats — round to 6dp in fixtures for byte-stable compare
    fx = dict(cells=cells0,
              final_cells={f"{a},{b},{c}": d for (a, b, c), d in cells.items()},
              tears=sev[:200],
              removed_total=len(removed),
              plan="4x4x6 block; 1 tap at (1.5,1.4,5.5); record density map, severed bonds",
              log=log)
    json.dump(fx, open("out/s02_fixture.json","w"), indent=1, sort_keys=True)
    json.dump(dict(bd=bd,
                   fatigue={f"{a},{b},{c}": v for (a, b, c), v in fatigue.items()},
                   sev=sev),
              open("out/s02_py_state.json", "w"), indent=1, sort_keys=True)
    print("fixture written; removed:", log[-1])

if __name__ == "__main__":
    gen_fixtures()
