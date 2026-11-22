"""DENT Stage 0.2 — surface extraction from the density-field rock.

Two deterministic extractors:
- extract_blocky(): raw voxel boundary faces (Stage 0.1-C style baseline).
- extract_mt():     marching tetrahedra over the trilinear density field
  (6 tets per cube, fixed mirrored decomposition, linear edge interpolation).
Deterministic: field eval, tet ordering, decomposition all fixed-order.
Vertices are output in WORLD fixed ints; normals from the field gradient
(central differences of the trilinear field) -> smooth shading without a
connectivity normal pass.
"""
import math
from common import FIX

ISO = 120  # extraction iso-level (matches DENS_ISO)


def field_at(rock, gx, gy, gz):
    """Density sampled at GRID NODE (i,j,k) = mean of the 2x2x2 cells around it."""
    d = rock.density
    acc = 0
    n = 0
    for dx in (-1, 0):
        for dy in (-1, 0):
            for dz in (-1, 0):
                v = d.get((gx+dx, gy+dy, gz+dz))
                if v is not None:
                    acc += v
                    n += 1
    return 0 if n == 0 else acc // n


def gradient(rock, x, y, z):
    """Central-difference gradient of trilinear density at world point."""
    h = rock.cs * 0.5
    f = rock.trilerp_density
    gx = f(x+h, y, z) - f(x-h, y, z)
    gy = f(x, y+h, z) - f(x, y-h, z)
    gz = f(x, y, z+h) - f(x, y, z-h)
    ln = math.sqrt(gx*gx + gy*gy + gz*gz) or 1.0
    return (gx/ln, gy/ln, gz/ln)


_FACETS = (  # the six cube faces as outward-wound corner quads
    ((1,0,0),(1,1,0),(1,1,1),(1,0,1)),
    ((0,0,0),(0,0,1),(0,1,1),(0,1,0)),
    ((0,1,0),(0,1,1),(1,1,1),(1,1,0)),
    ((0,0,0),(1,0,0),(1,0,1),(0,0,1)),
    ((0,0,0),(0,1,0),(1,1,0),(1,0,0)),
    ((0,0,1),(1,0,1),(1,1,1),(0,1,1)),
)
def _tets(i, j, k):
    """12 tetrahedra: six face-pyramids through the cube centre, each split
    into two tets. Bulletproof tiling; winding fixed geometrically in extract."""
    out = []
    for quad in _FACETS:
        cs = [(p[0]+i, p[1]+j, p[2]+k) for p in quad]
        a, b, c, d = cs
        ctr = (i+0.5, j+0.5, k+0.5)
        out.append((a, b, c, ctr))
        out.append((a, c, d, ctr))
    return out


def extract_mt(rock, want_normals=True):
    """Marching tetrahedra. Returns (verts_world_float, norms_float, tris) with
    verts shared via a dict keyed on rounded coords."""
    L = rock.L
    cs = rock.cs
    org = rock.origin
    # activity: only cubes adjacent to material cells + their shell
    active = set()
    for (i, j, k) in rock.density:
        for di in (-1, 0):
            for dj in (-1, 0):
                for dk in (-1, 0):
                    active.add((i+di, j+dj, k+dk))
    vcache = {}
    verts = []
    norms = []
    tris = []

    def node_val(p):
        if all(isinstance(v, int) for v in p):
            return field_at(rock, p[0], p[1], p[2])
        # fractional node (cube centre): mean of the 8 surrounding integer nodes
        i0, j0, k0 = int(math.floor(p[0])), int(math.floor(p[1])), int(math.floor(p[2]))
        fx, fy, fz = p[0]-i0, p[1]-j0, p[2]-k0
        acc = 0.0
        corners = (((i0,j0,k0),(1-fx)*(1-fy)*(1-fz)), ((i0+1,j0,k0),fx*(1-fy)*(1-fz)),
                   ((i0,j0+1,k0),(1-fx)*fy*(1-fz)), ((i0,j0,k0+1),(1-fx)*(1-fy)*fz),
                   ((i0+1,j0+1,k0),fx*fy*(1-fz)), ((i0+1,j0,k0+1),fx*(1-fy)*fz),
                   ((i0,j0+1,k0+1),(1-fx)*fy*fz), ((i0+1,j0+1,k0+1),fx*fy*fz))
        for q, w in corners:
            acc += field_at(rock, q[0], q[1], q[2]) * w
        return acc

    def node_world(p):
        return (org + p[0]*cs, org + p[1]*cs, org + p[2]*cs)

    def get_vert(p0, p1):
        f0, f1 = node_val(p0), node_val(p1)
        t = 0.5 if f1 == f0 else max(0.0, min(1.0, (ISO - f0) / (f1 - f0)))
        w0, w1 = node_world(p0), node_world(p1)
        x = w0[0] + t*(w1[0]-w0[0]); y = w0[1] + t*(w1[1]-w0[1]); z = w0[2] + t*(w1[2]-w0[2])
        key = (round(x*FIX), round(y*FIX), round(z*FIX))
        v = vcache.get(key)
        if v is None:
            v = len(verts)
            verts.append((x, y, z))
            if want_normals:
                nf = _grad_at(rock, x, y, z, cs)   # outward = -gradient (density high inside)
                norms.append(nf)
            vcache[key] = v
        return v

    for (i, j, k) in sorted(active):
        for tet in _tets(i, j, k):
            fv = [node_val(p) for p in tet[:3]]
            ctr = tet[3]
            fv.append(int(round(node_val(ctr))))
            inside = [f >= ISO for f in fv]
            ni = sum(inside)
            if ni == 0 or ni == 4:
                continue
            ins = [m for m in range(4) if inside[m]]
            outs = [m for m in range(4) if not inside[m]]
            pts = []
            for a in ins:
                for b in outs:
                    pts.append(get_vert(tet[a], tet[b]))
            ip = _ctr_world(ctr, org, cs)
            if ni == 1 or ni == 3:
                tri = _orient(rock, (pts[0], pts[1], pts[2]), verts, ip)
                tris.append(tri)
            else:  # ni == 2 -> quad from 4 crossing points
                q = (pts[0], pts[1], pts[3], pts[2])
                tris.append(_orient(rock, (q[0], q[1], q[2]), verts, ip))
                tris.append(_orient(rock, (q[0], q[2], q[3]), verts, ip))
    return verts, norms, tris


def _grad_at(rock, x, y, z, cs):
    g = gradient(rock, x, y, z)
    return (-g[0], -g[1], -g[2])   # outward normal


def _ctr_corner_iter(ctr):
    i, j, k = int(math.floor(ctr[0])), int(math.floor(ctr[1])), int(math.floor(ctr[2]))
    for dx in (i, i+1):
        for dy in (j, j+1):
            for dz in (k, k+1):
                yield (dx, dy, dz)


def _ctr_world(ctr, org, cs):
    return (org + ctr[0]*cs, org + ctr[1]*cs, org + ctr[2]*cs)


def _orient(rock, tri, verts, inside_pt):
    """Ensure the triangle faces away from the material interior point."""
    (v0, v1, v2) = tri
    a, b, c = verts[v0], verts[v1], verts[v2]
    ax = (b[0]-a[0], b[1]-a[1], b[2]-a[2])
    bx = (c[0]-a[0], c[1]-a[1], c[2]-a[2])
    nx = ax[1]*bx[2] - ax[2]*bx[1]
    ny = ax[2]*bx[0] - ax[0]*bx[2]
    nz = ax[0]*bx[1] - ax[1]*bx[0]
    ip = inside_pt
    np_x, np_y, np_z = ip[0]-a[0], ip[1]-a[1], ip[2]-a[2]
    if nx*np_x + ny*np_y + nz*np_z > 0:
        return (v0, v2, v1)
    return (v0, v1, v2)


def extract_blocky(rock):
    """Raw voxel boundary: quads on cell faces adjacent to void. World ints."""
    org, cs = rock.origin, rock.cs
    face_v = {}
    verts = []
    tris = []

    def vo(p):
        key = p
        v = face_v.get(key)
        if v is None:
            v = len(verts); face_v[key] = v
            verts.append(key)
        return v

    def quad(p0, p1, p2, p3):
        a, b, c, d = vo(p0), vo(p1), vo(p2), vo(p3)
        tris.append((a, b, c)); tris.append((a, c, d))

    L = rock.L
    for (i, j, k) in rock.density:
        x0 = round((org + i*cs)*FIX); x1 = round((org + (i+1)*cs)*FIX)
        y0 = round((org + j*cs)*FIX); y1 = round((org + (j+1)*cs)*FIX)
        z0 = round((org + k*cs)*FIX); z1 = round((org + (k+1)*cs)*FIX)
        if (i-1, j, k) not in rock.density:
            quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1))
        if (i+1, j, k) not in rock.density:
            quad((x1,y1,z0),(x1,y0,z0),(x1,y0,z1),(x1,y1,z1))
        if (i,j-1,k) not in rock.density:
            quad((x1,y0,z0),(x0,y0,z0),(x0,y0,z1),(x1,y0,z1))
        if (i,j+1,k) not in rock.density:
            quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1))
        if (i,j,k-1) not in rock.density:
            quad((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0))
        if (i,j,k+1) not in rock.density:
            quad((x1,y1,z1),(x0,y1,z1),(x0,y0,z1),(x1,y0,z1))
    return verts, tris


# ---------- incremental (local) extraction ----------

def extract_blocky_local(rock, dirty):
    """Blocky faces for cells in `dirty` only (plus any neighbour face shared
    with a dirty cell). Falls back to full duplicate verts — caller dedups by
    fixed coords. Returns (verts, tris)."""
    org, cs = rock.origin, rock.cs
    face_v = {}
    verts = []
    tris = []

    def vo(p):
        v = face_v.get(p)
        if v is None:
            v = len(verts); face_v[p] = v
            verts.append(p)
        return v

    def quad(p0, p1, p2, p3):
        a, b, c, d = vo(p0), vo(p1), vo(p2), vo(p3)
        tris.append((a, b, c)); tris.append((a, c, d))

    for (i, j, k) in dirty:
        if (i, j, k) not in rock.density:
            continue
        x0 = round((org+i*cs)*FIX); x1 = round((org+(i+1)*cs)*FIX)
        y0 = round((org+j*cs)*FIX); y1 = round((org+(j+1)*cs)*FIX)
        z0 = round((org+k*cs)*FIX); z1 = round((org+(k+1)*cs)*FIX)
        if (i-1, j, k) not in rock.density:
            quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1))
        if (i+1, j, k) not in rock.density:
            quad((x1,y1,z0),(x1,y0,z0),(x1,y0,z1),(x1,y1,z1))
        if (i,j-1,k) not in rock.density:
            quad((x1,y0,z0),(x0,y0,z0),(x0,y0,z1),(x1,y0,z1))
        if (i,j+1,k) not in rock.density:
            quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1))
        if (i,j,k-1) not in rock.density:
            quad((x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0))
        if (i,j,k+1) not in rock.density:
            quad((x1,y1,z1),(x0,y1,z1),(x0,y0,z1),(x1,y0,z1))
    return verts, tris


def extract_mt_local(rock, dirty, apron=1):
    """Marching tetrahedra restricted to a dirty box + `apron`-cell border.
    Because MT triangles are keyed on rounded fixed-point coordinates, boundary
    triangles of the local patch are bit-identical to the full extraction.
    Returns (verts, tris) covering only cells whose centre lies inside the box
    (apron cells contribute field values but not their own triangles)."""
    if not dirty:
        return [], [], []
    i0 = min(c[0] for c in dirty) - apron; i1 = max(c[0] for c in dirty) + apron
    j0 = min(c[1] for c in dirty) - apron; j1 = max(c[1] for c in dirty) + apron
    k0 = min(c[2] for c in dirty) - apron; k1 = max(c[2] for c in dirty) + apron
    box = lambda c: (i0 <= c[0] <= i1 and j0 <= c[1] <= j1 and k0 <= c[2] <= k1)
    inner = {c for c in dirty if box(c)}
    # reuse the full extractor by temporarily filtering the cell map
    saved = rock.density
    rock.density = {c: v for c, v in saved.items() if box(c)}
    try:
        verts, norms, tris = extract_mt(rock, want_normals=False)
    finally:
        rock.density = saved
    return verts, [], tris
