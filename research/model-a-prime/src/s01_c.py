"""Drop-in stand-in for the missing s01_c.ModelC voxelizer (scratch only).

The Stage 0.3 evidence bundle does not ship s01_c.py, so we reconstruct the
occupancy bitmap it must have produced: occ[cell]=1 for lattice cells whose
centre lies inside the star-shaped test boulder defined by common.rock_surface
(the same field gen_rock2 samples to build the mesh). boundary = solid cells
with at least one 6-neighbour empty.

Pure stdlib. Scratch experiment only.
"""
import math
import common


class ModelC:
    def __init__(self, verts, tris, lattice=96):
        self.L = lattice
        L = lattice
        origin = -1.05
        span = 2.10
        cs = span / L
        occ = [0] * (L * L * L)
        boundary = []
        for iy in range(L):
            for iz in range(L):
                base = iy * L + iz * L * L
                for ix in range(L):
                    wx = origin + (ix + 0.5) * cs
                    wy = origin + (iy + 0.5) * cs
                    wz = origin + (iz + 0.5) * cs
                    if _inside(wx, wy, wz):
                        occ[base + ix] = 1
        for iy in range(L):
            for iz in range(L):
                base = iy * L + iz * L * L
                for ix in range(L):
                    if not occ[base + ix]:
                        continue
                    if _any_empty(ix, iy, iz, occ, L):
                        boundary.append((ix, iy, iz))
        self.occ = occ
        self.boundary = boundary


def _inside(wx, wy, wz):
    n = math.sqrt(wx * wx + wy * wy + wz * wz)
    if n < 1e-12:
        return True
    dx, dy, dz = common.rock_surface(wx / n, wy / n, wz / n)
    return n <= math.sqrt(dx * dx + dy * dy + dz * dz)


def _any_empty(ix, iy, iz, occ, L):
    for a in (ix - 1, ix + 1):
        if a < 0 or a >= L or not occ[iy * L + iz * L * L + a]:
            return True
    for a in (iy - 1, iy + 1):
        if a < 0 or a >= L or not occ[a * L + iz * L * L + ix]:
            return True
    for a in (iz - 1, iz + 1):
        if a < 0 or a >= L or not occ[iy * L + a * L * L + ix]:
            return True
    return False
