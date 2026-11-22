"""DENT Stage 0.3 — RECON: surface-reconstruction method comparison.

Compares on the SAME damaged rock states (Stage 0.3 history snapshots at
alpha/Model-A calibration):

  1. MT  (marching tetrahedra — marching-cubes family, existing s02_mt)
  2. SN  (Surface Nets: naive dual — one vertex per sign-changing cell,
          vertices at average edge crossings; quads)
  3. DC  (Dual Contouring: per-cell vertex by QEF minimisation of Hermite
          plane equations from density-gradient normals; quads)

Metrics per state x method: verts, tris, extraction seconds, non-manifold
edge count. Renders: two angles per state x method.

Output: out/s03_recon_results.json ; PNGs out/s03_recon/
"""
import json, math, os, pickle, sys, time
from collections import Counter

sys.path.insert(0, '.')
from common import gen_rock2
import s03_rock as R3
import s03_hist as _SH  # for unpickling: HistStream was saved as __main__.HistStream
sys.modules['__main__'].HistStream = _SH.HistStream
import s02_mt as MT
import s02_render as RD

ISO = 120.0
OUT = "out/s03_recon"


def _cells_bbox(dens, L):
    imin = max(0, min(c[0] for c in dens) - 1); imax = min(L, max(c[0] for c in dens) + 2)
    jmin = max(0, min(c[1] for c in dens) - 1); jmax = min(L, max(c[1] for c in dens) + 2)
    kmin = max(0, min(c[2] for c in dens) - 1); kmax = min(L, max(c[2] for c in dens) + 2)
    return imin, imax, jmin, jmax, kmin, kmax


# ---------------- Surface Nets ----------------
def extract_sn(rock):
    dens = rock.density
    if not dens:
        return [], []
    imin, imax, jmin, jmax, kmin, kmax = _cells_bbox(dens, rock.L)
    org, cs = rock.origin, rock.cs

    def f(x, y, z):
        return rock.trilerp_density(x, y, z)
    verts = []
    nodes = {}
    for i in range(imin, imax):
        for j in range(jmin, jmax):
            for k in range(kmin, kmax):
                x0 = org + i * cs; y0 = org + j * cs; z0 = org + k * cs
                corner_vals = [f(x0, y0, z0), f(x0+cs, y0, z0), f(x0, y0+cs, z0), f(x0, y0, z0+cs),
                               f(x0+cs, y0+cs, z0), f(x0+cs, y0, z0+cs), f(x0, y0+cs, z0+cs),
                               f(x0+cs, y0+cs, z0+cs)]
                inside = [v >= ISO for v in corner_vals]
                if not (any(inside) and not all(inside)):
                    continue
                E = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4), (2, 6), (3, 5),
                     (3, 6), (4, 7), (5, 7), (6, 7)]
                C = [(x0, y0, z0), (x0+cs, y0, z0), (x0, y0+cs, z0), (x0, y0, z0+cs),
                     (x0+cs, y0+cs, z0), (x0+cs, y0, z0+cs), (x0, y0+cs, z0+cs), (x0+cs, y0+cs, z0+cs)]
                sx = sy = sz = 0.0; n = 0
                for a, b in E:
                    va, vb = corner_vals[a], corner_vals[b]
                    if (va >= ISO) == (vb >= ISO):
                        continue
                    t = 0.5 if vb == va else max(0.0, min(1.0, (ISO - va) / (vb - va)))
                    sx += C[a][0] + t * (C[b][0] - C[a][0])
                    sy += C[a][1] + t * (C[b][1] - C[a][1])
                    sz += C[a][2] + t * (C[b][2] - C[a][2])
                    n += 1
                if n:
                    verts.append((sx / n, sy / n, sz / n))
                    nodes[(i, j, k)] = len(verts) - 1
    tris = []
    for (i, j, k) in nodes:
        for d in range(3):
            if d == 0:
                a = (i, j, k); b = (i+1, j, k); c = (i, j+1, k); dd = (i+1, j+1, k)
            elif d == 1:
                a = (i, j, k); b = (i, j+1, k); c = (i, j, k+1); dd = (i, j+1, k+1)
            else:
                a = (i, j, k); b = (i+1, j, k); c = (i, j, k+1); dd = (i+1, j, k+1)
            if all(x in nodes for x in (a, b, c, dd)):
                va, vbq, vc, vd_ = nodes[a], nodes[b], nodes[c], nodes[dd]
                tris.append((va, vbq, vd_))
                tris.append((va, vd_, vc))
    return verts, tris


# ---------------- Dual Contouring ----------------
def extract_dc(rock):
    dens = rock.density
    if not dens:
        return [], []
    imin, imax, jmin, jmax, kmin, kmax = _cells_bbox(dens, rock.L)
    org, cs = rock.origin, rock.cs

    def f(x, y, z):
        return rock.trilerp_density(x, y, z)
    verts = []
    nodes = {}
    for i in range(imin, imax):
        for j in range(jmin, jmax):
            for k in range(kmin, kmax):
                x0 = org + i * cs; y0 = org + j * cs; z0 = org + k * cs
                C = [(x0, y0, z0), (x0+cs, y0, z0), (x0, y0+cs, z0), (x0, y0, z0+cs),
                     (x0+cs, y0+cs, z0), (x0+cs, y0, z0+cs), (x0, y0+cs, z0+cs), (x0+cs, y0+cs, z0+cs)]
                vals = [f(*p) for p in C]
                inside = [v >= ISO for v in vals]
                if not (any(inside) and not all(inside)):
                    continue
                E = [(0, 1), (0, 2), (0, 3), (1, 4), (1, 5), (2, 4), (2, 6), (3, 5),
                     (3, 6), (4, 7), (5, 7), (6, 7)]
                A = [[0.0] * 3 for _ in range(12)]
                b = [0.0] * 12
                m = 0
                for (a, bix) in E:
                    va, vb = vals[a], vals[bix]
                    if (va >= ISO) == (vb >= ISO):
                        continue
                    t = 0.5 if vb == va else max(0.0, min(1.0, (ISO - va) / (vb - va)))
                    px = C[a][0] + t * (C[bix][0] - C[a][0])
                    py = C[a][1] + t * (C[bix][1] - C[a][1])
                    pz = C[a][2] + t * (C[bix][2] - C[a][2])
                    e = 0.35 * cs
                    gx = f(px + e, py, pz) - f(px - e, py, pz)
                    gy = f(px, py + e, pz) - f(px, py - e, pz)
                    gz = f(px, py, pz + e) - f(px, py, pz - e)
                    gl = math.sqrt(gx*gx + gy*gy + gz*gz) or 1.0
                    s = 1.0 if va >= ISO else -1.0
                    A[m] = [s * gx / gl, s * gy / gl, s * gz / gl]
                    b[m] = A[m][0] * px + A[m][1] * py + A[m][2] * pz
                    m += 1
                M = [[0.0] * 3 for _ in range(3)]
                r = [0.0] * 3
                for q in range(m):
                    for a3 in range(3):
                        for b3 in range(3):
                            M[a3][b3] += A[q][a3] * A[q][b3]
                        r[a3] += A[q][a3] * b[q]
                DENS_RIDGE = cs * cs * 1e-4
                for a3 in range(3):
                    M[a3][a3] += DENS_RIDGE + 1e-9
                x3 = _solve3(M, r)
                if x3 is None:
                    x3 = [(C[0][q] + C[7][q]) * 0.5 for q in range(3)]
                verts.append(tuple(x3))
                nodes[(i, j, k)] = len(verts) - 1
    tris = []
    for (i, j, k) in nodes:
        for d in range(3):
            if d == 0:
                a = (i, j, k); b = (i+1, j, k); c = (i, j+1, k); dd = (i+1, j+1, k)
            elif d == 1:
                a = (i, j, k); b = (i, j+1, k); c = (i, j, k+1); dd = (i, j+1, k+1)
            else:
                a = (i, j, k); b = (i+1, j, k); c = (i, j, k+1); dd = (i+1, j, k+1)
            if all(x in nodes for x in (a, b, c, dd)):
                va, vbq, vc, vd_ = nodes[a], nodes[b], nodes[c], nodes[dd]
                tris.append((va, vbq, vd_))
                tris.append((va, vd_, vc))
    return verts, tris


def _solve3(M, r):
    A = [row[:] + [r[i]] for i, row in enumerate(M)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda q: abs(A[q][col]))
        if abs(A[piv][col]) < 1e-12:
            return None
        A[col], A[piv] = A[piv], A[col]
        for row in range(3):
            if row != col and A[row][col]:
                fr = A[row][col] / A[col][col]
                for cc in range(col, 4):
                    A[row][cc] -= fr * A[col][cc]
    return [A[q][3] / A[q][q] for q in range(3)]


# ---------------- metrics ----------------
def edge_defects(tris):
    deg = Counter()
    for (a, b, c) in tris:
        for e in ((a, b), (b, c), (c, a)):
            deg[frozenset(e)] += 1
    bad = sum(1 for v in deg.values() if v != 2)
    return bad, len(deg)


def load_rock(pkl):
    with open(pkl, "rb") as f:
        rock, hist_stream = pickle.load(f)
    rock._mat_cache = {}
    return rock


def main():
    os.makedirs(OUT, exist_ok=True)
    hp = "out/s03_hist"
    states = []
    for name, pth in (("histA_1M", os.path.join(hp, "A_concentrated", "state_1000000.pkl")),
                      ("histB_1M", os.path.join(hp, "B_distributed", "state_1000000.pkl")),
                      ("histC_1M", os.path.join(hp, "C_clustered", "state_1000000.pkl")),
                      ("histD_1M", os.path.join(hp, "D_edge", "state_1000000.pkl")),
                      ("histE_1M", os.path.join(hp, "E_adaptive", "state_1000000.pkl"))):
        if os.path.exists(pth):
            states.append((name, pth))
    out = []
    for name, pkl in states:
        rock = load_rock(pkl)
        res = {"state": name}
        t0 = time.time()
        mtv, _mtn, mtt = MT.extract_mt(rock)
        res["mt_seconds"] = round(time.time() - t0, 2)
        res["mt_verts"] = len(mtv); res["mt_tris"] = len(mtt)
        bad, tot = edge_defects(mtt)
        res["mt_edge_defects"] = f"{bad}/{tot}"
        t0 = time.time(); snv, snt = extract_sn(rock)
        res["sn_seconds"] = round(time.time() - t0, 2)
        res["sn_verts"] = len(snv); res["sn_tris"] = len(snt)
        bad, tot = edge_defects(snt)
        res["sn_edge_defects"] = f"{bad}/{tot}"
        t0 = time.time(); dcv, dct = extract_dc(rock)
        res["dc_seconds"] = round(time.time() - t0, 2)
        res["dc_verts"] = len(dcv); res["dc_tris"] = len(dct)
        bad, tot = edge_defects(dct)
        res["dc_edge_defects"] = f"{bad}/{tot}"
        out.append(res)
        print(json.dumps(res), flush=True)
        for meth, vv, tt in (("MT", mtv, mtt), ("SN", snv, snt), ("DC", dcv, dct)):
            if not tt:
                continue
            for ang, aname in (((0, 0, 1), "front"), ((1, 0.3, 0.6), "iso")):
                try:
                    RD.render_mesh(vv, tt, os.path.join(OUT, f"{name}_{meth}_{aname}.png"),
                                   size=420, view=ang, verts_world=False)
                except Exception as e:
                    print("render fail", name, meth, aname, repr(e), flush=True)
    json.dump(out, open("out/s03_recon_results.json", "w"), indent=1)
    print("recon done", flush=True)


if __name__ == "__main__":
    main()
