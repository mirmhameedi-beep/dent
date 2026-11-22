"""DENT Stage 0.2 — flexible software renderer.
Orthographic triangle rasterizer with arbitrary camera direction, zoom,
target point, cutaway clipping, warm-grey matte stone shading, z-buffer.
Pure stdlib. Deterministic for fixed input.
"""
import math
import struct
import zlib
from common import write_png, FIX

BG = (10, 10, 12)
STONE_HI = (196, 190, 182)
STONE_LO = (60, 58, 55)
CUT_RGB = (112, 108, 104)   # exposed fracture/cut material tone


def _basis(view_dir, up=(0, 1, 0)):
    f = _norm(view_dir)             # forward = direction camera looks
    r = _norm(_cross(f, up)) or _norm(_cross(f, (0, 0, 1)))
    u = _norm(_cross(r, f))
    return r, u, f


def _norm(v):
    n = math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]) or 1.0
    return (v[0]/n, v[1]/n, v[2]/n)


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def render_mesh(verts, tris, path, size=420, view=(0, 0, 1), zoom=1.0,
                target=(0.0, 0.0, 0.0), sun=(0.45, 0.62, 0.66), fill=1.0,
                cut=None, cut_rgb=CUT_RGB, verts_world=True):
    """verts: fixed-int world (or float world if verts_world=False).
    view: direction from camera toward scene (front view => (0,0,1) means
    camera on -z side looking +z; we project onto plane perpendicular to view).
    zoom: 1 = whole rock; 2 = 2x close-up.
    target: world float point at image centre.
    cut: optional (axis 0/1/2, plane_world_float): hide material beyond plane.
    """
    vx, vy, vz = view
    r, u, f = _basis(view)
    scale = size / 2.3 * zoom

    def prep(v):
        if verts_world:
            x, y, z = v[0]/FIX, v[1]/FIX, v[2]/FIX
        else:
            x, y, z = v
        rel = (x-target[0], y-target[1], z-target[2])
        # screen space: pixel coords (y flipped); depth stays world units
        return (size/2 + (rel[0]*r[0]+rel[1]*r[1]+rel[2]*r[2]) * scale,
                size/2 - (rel[0]*u[0]+rel[1]*u[1]+rel[2]*u[2]) * scale,
                rel[0]*f[0]+rel[1]*f[1]+rel[2]*f[2])

    zbuf = [[1e18]*size for _ in range(size)]
    img = [[BG]*size for _ in range(size)]
    # vertex normals via connectivity
    normals = {i: [0.0, 0.0, 0.0] for i in range(len(verts))}
    for (a, b, c) in tris:
        px = _cross((verts[b][0]-verts[a][0], verts[b][1]-verts[a][1], verts[b][2]-verts[a][2]),
                    (verts[c][0]-verts[a][0], verts[c][1]-verts[a][1], verts[c][2]-verts[a][2]))
        for m in (a, b, c):
            n = normals[m]
            n[0] += px[0]; n[1] += px[1]; n[2] += px[2]
    for m, n in normals.items():
        ln = math.sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]) or 1.0
        normals[m] = (n[0]/ln, n[1]/ln, n[2]/ln)

    sunl = _norm(sun)
    for (a, b, c) in tris:
        px, py, pz = prep(verts[a]); qx, qy, qz = prep(verts[b]); sx, sy, sz = prep(verts[c])
        if cut is not None:
            axis, plane = cut
            vals = []
            for v in (verts[a], verts[b], verts[c]):
                w = (v[0]/FIX, v[1]/FIX, v[2]/FIX) if verts_world else v
                vals.append(w[axis] - plane)
            # skip if fully beyond the plane
            if all(x > 0 for x in vals):
                continue
        cx = size/2; cy = size/2
        minx = max(0, int(min(px, qx, sx)))
        maxx = min(size-1, int(max(px, qx, sx))+1)
        miny = max(0, int(min(py, qy, sy)))
        maxy = min(size-1, int(max(py, qy, sy))+1)
        if minx > maxx or miny > maxy:
            continue
        den = (qy-sy)*(px-sx) + (sx-qx)*(py-sy)
        if abs(den) < 1e-12:
            continue
        for yy in range(miny, maxy+1):
            for xx in range(minx, maxx+1):
                l0 = ((qy-sy)*(xx-sx) + (sx-qx)*(yy-sy)) / den
                l1 = ((sy-py)*(xx-sx) + (px-sx)*(yy-sy)) / den
                l2 = 1 - l0 - l1
                if l0 < -1e-9 or l1 < -1e-9 or l2 < -1e-9:
                    continue
                if l0 > 1+1e-9 or l1 > 1+1e-9 or l2 > 1+1e-9:
                    continue
                depth = l0*pz + l1*qz + l2*sz
                xx_i, yy_i = xx, yy
                if depth < zbuf[yy_i][xx_i]:   # nearest surface wins
                    zbuf[yy_i][xx_i] = depth
                    nx = l0*normals[a][0] + l1*normals[b][0] + l2*normals[c][0]
                    ny = l0*normals[a][1] + l1*normals[b][1] + l2*normals[c][1]
                    nz = l0*normals[a][2] + l1*normals[b][2] + l2*normals[c][2]
                    # two-sided shading: flip normals that point away from camera
                    if nx*f[0] + ny*f[1] + nz*f[2] > 0:
                        nx, ny, nz = -nx, -ny, -nz
                    # Lambert, camera forward = -f; view-normal aligns to -f
                    lam = max(0.05, -(nx*f[0] + ny*f[1] + nz*f[2]))
                    lam2 = max(0.0, nx*sunl[0] + ny*sunl[1] + nz*sunl[2])
                    rim = max(0.0, nx*r[0] + ny*r[1] + nz*r[2])
                    base = 30 + 165*lam2 + 22*lam + 26*rim*(1-lam2)
                    col = (min(255, base*1.03), min(255, base*0.99), min(255, base*0.95))
                    if cut is not None and _tri_at_cut((verts[a], verts[b], verts[c]), cut, verts_world):
                        col = cut_rgb
                    img[yy_i][xx_i] = col
    write_png(path, size, size, lambda x, y: img[y][x])
    return path


def _tri_at_cut(verts3, cut, verts_world):
    """A triangle lies ON the cut if all its verts are at/below the plane and
    at least one exactly at plane -> it's a cross-section face. We approximate:
    faces touching the plane count as cut faces."""
    axis, plane = cut
    at = 0
    for v in verts3:
        w = (v[0]/FIX, v[1]/FIX, v[2]/FIX) if verts_world else v
        d = w[axis] - plane
        if d > 0:
            return False
        if abs(d) < 1e-6:
            at += 1
    return at >= 1


def render_blocky_cutaway(rock, axis, plane_cell, path, size=420, view=(0, 0, 1),
                          zoom=1.0):
    """Direct voxel cross-section render: cut faces drawn from the cell slice."""
    from s02_mt import extract_blocky
    # faces at cells with cell[axis] == plane_cell-? : draw as flat quads via render_mesh:
    plane_w = rock.origin + (plane_cell) * rock.cs
    verts, tris = extract_blocky(rock)
    # drop material beyond plane
    keep = []
    for (a, b, c) in tris:
        px = (verts[a][0]/FIX, verts[a][1]/FIX, verts[a][2]/FIX)
        if all((px[axis] if i == axis else 1) - plane_w <= 0 for i in [axis]):
            pass
        vv = [(verts[a][0]/FIX, verts[a][1]/FIX, verts[a][2]/FIX),
              (verts[b][0]/FIX, verts[b][1]/FIX, verts[b][2]/FIX),
              (verts[c][0]/FIX, verts[c][1]/FIX, verts[c][2]/FIX)]
        if min(v[axis] - plane_w for v in vv) > 0:
            continue
        keep.append((a, b, c))
    return render_mesh(verts, keep, path, size=size, view=view, zoom=zoom,
                       cut=(axis, plane_w))
