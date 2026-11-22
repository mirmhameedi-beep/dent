"""Dent Stage 0 PoC - shared geometry, fixed-point, rendering, serialization utils.

Pure stdlib. Deterministic. All persisted geometry math is integer fixed-point:
world coords are stored as int32 units of 1/65536 (FIX=65536). Diameter D=2.0 world.
"""
import hashlib
import json
import math
import random
import struct
import time
import zlib

FIX = 65536          # fixed-point denominator (1/65536 world units)
D_FIXED = 2 * FIX    # diameter in fixed units (D = 2.0)
LATTICE = 128        # experiment lattice (cells across bounding cube)
CELL_D = D_FIXED // LATTICE  # cell width in fixed units (≈0.0102 world = 0.51% D)
KER_R = 2            # kernel radius in cells -> crater radius ≈ 1.0% D
SAT = 8000           # int16 range accumulator saturation depth (retained)
# K_DISP: fixed units of vertex sink per retained-depth unit.
# max sink = SAT * K_DISP / FIX = 8000*2/65536 = 0.244 world = 12.2% of D (D=2.0).
# Historical bug: K_DISP=64 gave max sink 7.8 world units = 3.9*D (nonsense). Now 2.
K_DISP = 2
FAIL_AT = 6400       # depth at which a surface cell fails (material leaves)


# ---------- deterministic value noise (integer hash) ----------
def _ihash3(x, y, z, seed):
    h = (x * 374761393 + y * 668265263 + z * 2147483647 + seed * 97) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFFFF) / 0xFFFFFFFF


def vnoise3(x, y, z, seed=0):
    """Trilinear-interpolated value noise on integer lattice."""
    xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
    fx, fy, fz = x - xi, y - yi, z - zi
    def s(t):
        return t * t * (3 - 2 * t)
    sx, sy, sz = s(fx), s(fy), s(fz)
    acc = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (sx if dx else 1 - sx) * (sy if dy else 1 - sy) * (sz if dz else 1 - sz)
                acc += w * _ihash3(xi + dx, yi + dy, zi + dz, seed)
    return acc


# ---------- test rock: quadsphere, flattened faces, concavities, narrow crevice ----------
# SLOT_HALF is in WORLD units: full crevice gap = 2 * 1.6 cells wide (3.2 cells).
# The crevice is a narrow slab around the plane y = 0.3*x (unit normal below),
# restricted to a footprint so it cuts one arc of the surface. (Historical bug:
# the original band |x|,|z|<0.55, |y|<0.025 never intersected a radius~1
# quadsphere surface at all, so no crevice existed; fixed with a plane cut.)
SLOT_HALF = 1.6 * CELL_D / FIX   # world half-gap = 0.025 (gap = 0.05 = 3.2 cells)
_SLOT_NX, _SLOT_NY = -0.3 / math.sqrt(1.09), 1.0 / math.sqrt(1.09)


def slot_sign(px, py, pz):
    """Signed distance to the crevice plane (world units)."""
    return py * _SLOT_NY + px * _SLOT_NX


def _slot_clamp(px, py, pz):
    """Push surface points inside the crevice slab onto its two parallel walls.

    px, py, pz are WORLD units (a surface point of the boulder). Material may
    only exist at signed distance >= +SLOT_HALF or <= -SLOT_HALF from the
    crevice plane, inside the footprint px < 0.55 and -0.05 < py < 0.72. A
    point inside the gap band is displaced perpendicular to the plane onto the
    nearer wall (sign of its signed distance). The two wall strips face each
    other across an empty 2*SLOT_HALF-wide slab and are NOT surface-adjacent.
    """
    s = slot_sign(px, py, pz)
    if abs(s) < SLOT_HALF and px < 0.55 and -0.05 < py < 0.72:
        target = math.copysign(SLOT_HALF, s if s != 0 else 1.0)
        delta = target - s
        return px + _SLOT_NX * delta, py + _SLOT_NY * delta, pz
    return px, py, pz


_ROT_AXIS = (1.0, 0.3, 0.7)
_ROT_T = 0.021   # rad; generic-axis micro-rotation so no face-grid row lies
                 # exactly on the slot plane y=0 (keeps both crevice walls)


def _rot(dx, dy, dz):
    ax, ay, az = _ROT_AXIS
    l = math.sqrt(ax * ax + ay * ay + az * az)
    ax, ay, az = ax / l, ay / l, az / l
    c, s = math.cos(_ROT_T), math.sin(_ROT_T)
    d = (ax * dx + ay * dy + az * dz) * (1 - c)
    return (
        dx * c + (ay * dz - az * dy) * s + ax * d,
        dy * c + (az * dx - ax * dz) * s + ay * d,
        dz * c + (ax * dy - ay * dx) * s + az * d,
    )


def rock_surface(x, y, z):
    """Radius field of the test boulder for direction (x,y,z)."""
    n = math.sqrt(x * x + y * y + z * z) or 1e-12
    dx, dy, dz = _rot(x / n, y / n, z / n)
    # flatten faces slightly (cubeness) -> large faces and curved creases
    m = max(abs(dx), abs(dy), abs(dz))
    flat = 1.0 - 0.16 * (1.0 - m)
    r = 1.0 * flat
    r *= 1.0 + 0.34 * (vnoise3(dx * 2.1 + 9, dy * 2.1 + 3, dz * 2.1 + 7, 11) - 0.5)
    r *= 1.0 + 0.14 * (vnoise3(dx * 5.3, dy * 5.3 + 4, dz * 5.3, 23) - 0.5)
    # two concave dimples
    for (ca, cb, cc, w, d) in ((0.55, 0.5, 0.6, 0.34, 0.11), (-0.5, -0.35, 0.7, 0.30, 0.08)):
        dot = dx * ca + dy * cb + dz * cc
        if dot > 0:
            r -= d * (dot ** 6) * w * 12
    # narrow crevice: clamp into slot band near the top-front region
    px, py, pz = dx * r, dy * r, dz * r
    px, py, pz = _slot_clamp(px, py, pz)
    return px, py, pz


def _face_point(fi, i, j, n):
    # (Historical bug: fi=3,4,5 aliased the planes of fi=0,1,2 with swapped axes,
    # producing a doubly-covered non-manifold surface. Now the six distinct
    # cube faces; winding normalized below in gen_rock2.)
    u = -1 + 2 * i / n
    v = -1 + 2 * j / n
    if fi == 0:
        return (u, v, 1.0)
    if fi == 1:
        return (u, -1.0, v)
    if fi == 2:
        return (1.0, u, v)
    if fi == 3:
        return (u, v, -1.0)
    if fi == 4:
        return (u, 1.0, v)
    return (-1.0, u, v)


def gen_rock2(n=48):
    """Clean single-pass welded quadsphere boulder."""
    pos2idx = {}
    verts = []
    idx_grid = {}
    for fi in range(6):
        for j in range(n + 1):
            for i in range(n + 1):
                fx, fy, fz = _face_point(fi, i, j, n)
                q = (round(fx * LATTICE), round(fy * LATTICE), round(fz * LATTICE))
                if q not in pos2idx:
                    sx, sy, sz = rock_surface(fx, fy, fz)
                    pos2idx[q] = len(verts)
                    verts.append((round(sx * FIX), round(sy * FIX), round(sz * FIX)))
                idx_grid[(fi, j, i)] = pos2idx[q]
    tris = []
    for fi in range(6):
        for j in range(n):
            for i in range(n):
                a = idx_grid[(fi, j, i)]
                b = idx_grid[(fi, j, i + 1)]
                c = idx_grid[(fi, j + 1, i + 1)]
                d = idx_grid[(fi, j + 1, i)]
                tris.append((a, b, c))
                tris.append((a, c, d))
    # normalize winding outward (rock is star-shaped about the origin)
    fixed = []
    for a, b, c in tris:
        ax, ay, az = verts[a]; bx, by, bz = verts[b]; cx, cy, cz = verts[c]
        e1 = (bx - ax, by - ay, bz - az)
        e2 = (cx - ax, cy - ay, cz - az)
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        mx, my, mz = (ax + bx + cx) / 3, (ay + by + cy) / 3, (az + bz + cz) / 3
        if nx * mx + ny * my + nz * mz < 0:
            fixed.append((a, c, b))
        else:
            fixed.append((a, b, c))
    return verts, fixed


# ---------- topology (adjacency) ----------
def adjacency(verts, tris):
    adj = [set() for _ in verts]
    for a, b, c in tris:
        adj[a].add(b); adj[a].add(c)
        adj[b].add(a); adj[b].add(c)
        adj[c].add(a); adj[c].add(b)
    return [sorted(s) for s in adj]


def vertex_normals_with(verts, tris):
    acc = [[0.0, 0.0, 0.0] for _ in verts]
    for a, b, c in tris:
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        e1 = (bx - ax, by - ay, bz - az)
        e2 = (cx - ax, cy - ay, cz - az)
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        acc[a][0] += nx; acc[a][1] += ny; acc[a][2] += nz
        acc[b][0] += nx; acc[b][1] += ny; acc[b][2] += nz
        acc[c][0] += nx; acc[c][1] += ny; acc[c][2] += nz
    out = []
    for v in acc:
        l = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1e-12
        out.append((v[0] / l, v[1] / l, v[2] / l))
    return out


# ---------- raycast (Möller–Trumbore), pure python ----------
def raycast(orig, d, verts, tris):
    """orig, d: fixed-int tuples. Returns (tri_idx, t_fixed, u, v) or None; d normalized float."""
    ox, oy, oz = orig
    dx, dy, dz = d
    best = None
    for ti, (a, b, c) in enumerate(tris):
        ax, ay, az = verts[a]
        bx, by, bz = verts[b]
        cx, cy, cz = verts[c]
        e1 = (bx - ax, by - ay, bz - az)
        e2 = (cx - ax, cy - ay, cz - az)
        px, py, pz = dy * e2[2] - dz * e2[1], dz * e2[0] - dx * e2[2], dx * e2[1] - dy * e2[0]
        det = e1[0] * px + e1[1] * py + e1[2] * pz
        if -1e-12 < det < 1e-12:
            continue
        inv = 1.0 / det
        tox, toy, toz = ox - ax, oy - ay, oz - az
        u = (tox * px + toy * py + toz * pz) * inv
        if u < -1e-9 or u > 1 + 1e-9:
            continue
        qx, qy, qz = toy * e1[2] - toz * e1[1], toz * e1[0] - tox * e1[2], tox * e1[1] - toy * e1[0]
        vv = (dx * qx + dy * qy + dz * qz) * inv
        if vv < -1e-9 or u + vv > 1 + 1e-9:
            continue
        t = (e2[0] * qx + e2[1] * qy + e2[2] * qz) * inv
        if t <= 0:
            continue
        if best is None or t < best[1]:
            best = (ti, t, u, vv)
    return best


# ---------- fixed-point helpers ----------
def round_half_even(x):
    f = math.floor(x)
    diff = x - f
    if diff > 0.5:
        return f + 1
    if diff < 0.5:
        return f
    return f if f % 2 == 0 else f + 1


def to_fixed(v):
    return round_half_even(v * FIX)


# ---------- canonical serialization ----------
def sha_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_field_bytes(field_flat_items):
    """field_flat_items: iterable of (cell_key, depth_int) — key int64 packed little-endian + int16 depth."""
    items = sorted(field_flat_items)
    h = hashlib.sha256()
    for key, depth in items:
        h.update(struct.pack("<qh", key, depth))
    return h.hexdigest()


def write_png(path, w, h, get_rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b = get_rgb(x, y)
            raw += bytes((max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b)))))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 6))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)


# ---------- software render (orthographic, Lambert, zbuffer) ----------
def render(verts, tris, path, size=340, sun=(0.45, 0.6, 0.66), damage_color=None):
    """damage_color: optional callable(tri_idx, bary_at_pixel)->(r,g,b) tint override."""
    # orthographic: project x,z to image, depth = -y toward camera along -y? choose camera at +z.
    cx = cy = size / 2
    scale = size / 2.3
    zbuf = [[-1e18] * size for _ in range(size)]
    img = [[(8, 8, 10)] * size for _ in range(size)]
    fn = vertex_normals_with(verts, tris)
    for ti, (a, b, c) in enumerate(tris):
        va, vb, vc = verts[a], verts[b], verts[c]
        def proj(v):
            return (cx + v[0] / FIX * scale, cy - v[1] / FIX * scale, v[2] / FIX)
        x0, y0, z0 = proj(va)
        x1, y1, z1 = proj(vb)
        x2, y2, z2 = proj(vc)
        minx = max(0, int(min(x0, x1, x2)))
        maxx = min(size - 1, int(max(x0, x1, x2)) + 1)
        miny = max(0, int(min(y0, y1, y2)))
        maxy = min(size - 1, int(max(y0, y1, y2)) + 1)
        if minx > maxx or miny > maxy:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        for py in range(miny, maxy + 1):
            for px in range(minx, maxx + 1):
                l0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
                l1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
                l2 = 1 - l0 - l1
                if l0 < -1e-9 or l1 < -1e-9 or l2 < -1e-9:
                    continue
                z = l0 * z0 + l1 * z1 + l2 * z2
                if z > zbuf[py][px]:
                    zbuf[py][px] = z
                    nx = l0 * fn[a][0] + l1 * fn[b][0] + l2 * fn[c][0]
                    ny = l0 * fn[a][1] + l1 * fn[b][1] + l2 * fn[c][1]
                    nz = l0 * fn[a][2] + l1 * fn[b][2] + l2 * fn[c][2]
                    lam = max(0.0, nx * sun[0] + ny * sun[1] + nz * sun[2])
                    base = 26 + 150 * lam
                    col = (base * 1.02, base, base * 0.98)
                    if damage_color is not None:
                        tint = damage_color(ti, (l0, l1, l2), lam, base)
                        if tint is not None:
                            col = tint
                    img[py][px] = col
    write_png(path, size, size, lambda x, y: img[y][x])
    return path
