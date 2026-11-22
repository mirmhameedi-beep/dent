"""DENT Stage 0.2 — density-field sparse voxel rock with bond-lattice fracture.

Design (differs from Stage 0.1 model C):
- Each sparse grid cell holds a DENSITY (0..DENS_MAX), not just solid/void.
  Impacts carve density away first (smooth depressions), cells crumble only
  when density drops below DENS_FAIL -> real material removal + interior.
- A deterministic BOND LATTICE (rigid-body-spring-model lite) links every pair
  of 6-adjacent material voxels. Impacts damage bonds (scaled by local material
  toughness); bonds sever at zero damage budget. Fracture EMERGES from severed
  bonds: no prescribed cuts anywhere in this engine.
- Per-cell material properties (hardness, toughness, slight density variation)
  come from deterministic integer value noise -> geology varies across the rock.
- Ray resolution: DDA against density>0, refined to the trilinear iso-surface
  so taps hit the CURRENT visible surface, not the original one.
- Fragments: connectivity over live bonds from a core seed; detached groups
  become fragments (removed from the main body, retained as fragment objects).
- All state fixed-point ints; canonical hashing for determinism tests.

Pure stdlib. Deterministic. Scratch experiment only — NOT product code.
"""
import math
import time
from common import vnoise3, FIX

DENS_MAX = 240          # full material density (integer)
DENS_FAIL = 30          # below this the cell crumbles (material leaves)
DENS_ISO = 120          # iso-level for surface extraction (half of full)

# Material constants (tuned by hand, then measured; not scientific geology)
K_COMPRESS = 2.6        # density removed at impact centre (bore-through ~5e3 taps)
K_BOND = 90             # bond damage at impact centre
BOND_STRENGTH = 1000    # bond severs when damage >= BOND_STRENGTH * local toughness
SC_PROP = 240           # stress-concentration transferred to sibling bonds of a severed bond
R_IMPACT = 2.6          # impact influence radius in cells
R_BOND = 2.2            # bond damage influence radius in cells
FATIGUE = 0.14          # fraction of previous-toughness lost per unit damage (dependency below)
FATIGUE_K = 0.00012     # toughness *= (1 - FATIGUE_K * accumulated bond damage)

_NEIGH6 = ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))
_BDIR = _NEIGH6[:3]     # canonical bond directions (+x,+y,+z) to avoid duplicates


def vkey(i, j, k, L):
    # no +1 offset: (i+1) wraps under vunkey's % L for i == L-1 (97-face bug)
    return i + j * L + k * L * L

def vunkey(v, L):
    return (v % L, (v // L) % L, v // (L * L))


class MaterialField:
    """Deterministic geological variation: hardness (resists compression),
    toughness (resists bond failure), density variation. Noise-seeded."""
    def __init__(self, seed=7):
        self.seed = seed
    def hardness(self, i, j, k):
        n = vnoise3(i * 0.055, j * 0.055, k * 0.055, self.seed)          # broad banding
        n2 = vnoise3(i * 0.25, j * 0.25, k * 0.25, self.seed + 101)      # grain
        return 0.7 + 0.8 * n + 0.25 * n2                                  # ~0.70..1.75
    def toughness(self, i, j, k):
        n = vnoise3(i * 0.045, j * 0.045, k * 0.045, self.seed + 17)
        n2 = vnoise3(i * 0.25, j * 0.25, k * 0.25, self.seed + 211)
        return 0.7 + 0.9 * n + 0.2 * n2                                   # ~0.70..1.80
    def density_var(self, i, j, k):
        return 0.92 + 0.08 * vnoise3(i * 0.25, j * 0.25, k * 0.25, self.seed + 301)


class RockDensity:
    def __init__(self, verts, tris, lattice=96, cover_iters=3):
        self.L = lattice
        self.origin = -1.05
        self.span = 2.10
        self.cs = self.span / self.L
        self.mat = MaterialField()
        self.density = {}            # (i,j,k) -> int density  (sparse)
        self.bdamage = {}            # packed bond key -> int damage
        self.severed = set()         # packed bond keys of severed bonds
        self.fatigue = {}            # packed cell key -> accumulated fatigue units
        # stats
        self.s = dict(taps=0, rejected=0, fragments=[], sev_total=0,
                      mass_removed=0, mass_applied=0, crumbles=0)
        self.times = dict(ray=0.0, impact=0.0, conn=0.0, extract=0.0)
        # occupancy from parity voxelizer (reuse s01_c's proven scanline code)
        import s01_c
        probe = s01_c.ModelC(verts, tris, lattice=lattice)
        self.occ_init = probe.occ
        self.boundary_init = set(probe.boundary)
        self._init_density()
        del probe
        self._cover(cover_iters)
        self.core = self._seed_core()
        self._dirty_cells = set()
        self._mat_cache = {}
        self._sc_queue = []

    # ---------- construction ----------
    def _init_density(self):
        L = self.L
        occ = self.occ_init
        for iy in range(L):
            base = iy * L
            for iz in range(L):
                base2 = (base + iz * L * L)
                for ix in range(L):
                    if occ[base2 + ix]:
                        i, j, k = ix, iy, iz
                        m = self.mat.density_var(i, j, k)
                        # boundary cells start slightly eroded (natural rounding):
                        d = int(round(DENS_MAX * m))
                        self.density[(i, j, k)] = d

    def _cover(self, iters):
        """Smooth the pristine surface: boundary-cell density from sparse
        coverage of inside. Produces a rounder iso-surface for MT."""
        L, cs, org = self.L, self.cs, self.origin
        occ = self.occ_init
        new = {}
        cells = sorted(self.density)
        cell_set = set(cells)
        for it in range(iters):
            for c in cells:
                i, j, k = c
                solid_n = 0
                ssum = 0
                for dx, dy, dz in _NEIGH6:
                    n = (i+dx, j+dy, k+dz)
                    if n in cell_set:
                        solid_n += 1
                        ssum += self.density[n]
                cur = self.density[c]
                if solid_n < 6:
                    # boundary cell: density biased toward (avg neighbour density)
                    avg = ssum / solid_n if solid_n else 0
                    f = 0.5 + 0.18 * it   # relax: 0.5,0.68,0.86
                    target = cur * f + avg * (1 - f) if solid_n else 0
                    new[c] = max(8, int(round(target * (cur / DENS_MAX) ** 0.25)))
                else:
                    new[c] = cur
            self.density = new
            cells = sorted(self.density)
        # crumble any now-invalid cells
        dead = [c for c, d in self.density.items() if d < DENS_FAIL]
        for c in dead:
            self._prune_cell(c)

    def _prune_cell(self, c):
        self.density.pop(c, None)
        self.fatigue.pop(vkey(*c, self.L), None)

    def _seed_core(self):
        # volumetric centre-ish well-connected cell
        best = max(self.density, key=lambda c: self.density[c])
        return best

    def hardness(self, c):
        v = self._mat_cache.get(c)
        if v is None:
            v = self.mat.hardness(*c)
            self._mat_cache[c] = v
        return v

    def toughness(self, c):
        v = self._mat_cache.get((c, 't'))
        if v is None:
            v = self.mat.toughness(*c)
            self._mat_cache[(c, 't')] = v
        return v

    def bonds_of(self, c):
        """Yield (bond_key, neighbour_cell) for live (non-severed, both-solid) bonds."""
        L = self.L
        i, j, k = c
        for dx, dy, dz in _BDIR:
            n = (i+dx, j+dy, k+dz)
            if n in self.density:
                va, vb = vkey(*c, L), vkey(*n, L)
                if va > vb:
                    va, vb = vb, va
                key = (va << 24) | vb
                if key not in self.severed:
                    yield key, n

    def _local_material(self, c):
        """Effective current toughness reduced by fatigue."""
        base = self.toughness(c)
        f = self.fatigue.get(vkey(*c, self.L), 0)
        return base * max(0.05, 1.0 - FATIGUE_K * f)

    # ---------- surface / ray ----------
    def is_solid(self, c):
        return c in self.density

    def density_at(self, i, j, k):
        return self.density.get((i, j, k), 0)

    def trilerp_density(self, x, y, z):
        """World coords -> interpolated density (grid nodes at cell centres)."""
        L, cs, org = self.L, self.cs, self.origin
        fx = (x - org) / cs - 0.5
        fy = (y - org) / cs - 0.5
        fz = (z - org) / cs - 0.5
        i, j, k = math.floor(fx), math.floor(fy), math.floor(fz)
        tx, ty, tz = fx - i, fy - j, fz - k
        acc = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    w = (tx if dx else 1-tx) * (ty if dy else 1-ty) * (tz if dz else 1-tz)
                    acc += w * self.density_at(i+dx, j+dy, k+dz)
        return acc

    def resolve_ray(self, orig, d):
        """orig,d fixed-int 3D. DDA over density>0; refine via trilerp bisection.
        Returns (world_hit_fixed_xyz, cell) or None. Hits the CURRENT surface."""
        L, cs, org = self.L, self.cs, self.origin
        ox, oy, oz = orig
        dx_, dy_, dz_ = d
        ln = math.sqrt(dx_ * dx_ + dy_ * dy_ + dz_ * dz_) or 1
        dx_, dy_, dz_ = dx_ / ln, dy_ / ln, dz_ / ln
        def solid_world(wx, wy, wz):
            i = int(math.floor((wx / FIX - org) / cs))
            j = int(math.floor((wy / FIX - org) / cs))
            k = int(math.floor((wz / FIX - org) / cs))
            if i < 0 or j < 0 or k < 0 or i >= L or j >= L or k >= L:
                return None
            return (i, j, k) if (i, j, k) in self.density else None
        # DDA over cell lattice
        wi, wj, wk = ox / FIX, oy / FIX, oz / FIX     # world float
        i = int(math.floor((wi - org) / cs)); j = int(math.floor((wj - org) / cs)); k = int(math.floor((wk - org) / cs))
        tmax = [0.0, 0.0, 0.0]; td = [0.0, 0.0, 0.0]
        step = [0, 0, 0]
        t_enter = 0.0
        pos = [wi, wj, wk]
        contact = None
        for axis in range(3):
            if d[axis] == 0:
                tmax[axis] = 1e30; td[axis] = 1e30; step[axis] = 0
            else:
                nxt = org + ((pos[axis] - org) // cs + (1 if d[axis] > 0 else 0)) * cs
                # better: next cell boundary
                ci = int(math.floor((pos[axis] - org) / cs))
                nb = org + (ci + 1) * cs if d[axis] > 0 else org + ci * cs
                tmax[axis] = abs((nb - pos[axis]) / (d[axis] / FIX * ln / ln)) * 1.0  # world units along ray
                tmax[axis] = (nb - pos[axis]) / (d[axis] / FIX)
                td[axis] = abs(cs / (d[axis] / FIX))
                step[axis] = 1 if d[axis] > 0 else -1
        for _ in range(3 * L + 8):
            if 0 <= i < L and 0 <= j < L and 0 <= k < L and (i, j, k) in self.density:
                contact = (i, j, k)
                break
            # step to smallest tmax
            m = tmax[0]
            ax = 0
            if tmax[1] < m: m = tmax[1]; ax = 1
            if tmax[2] < m: m = tmax[2]; ax = 2
            if m > self.span * 2.2:
                break
            if ax == 0: i += step[0]
            elif ax == 1: j += step[1]
            else: k += step[2]
            tmax[ax] += td[ax] if td[ax] < 1e29 else 1.0
            if td[ax] < 1e29:
                t_enter = m
        if contact is None:
            return None
        # refine to the FIRST iso crossing after t_enter (the current visible
        # surface). lo starts in the air cell just before contact; hi is the
        # contact cell centre. Never crosses into interior walls beyond it.
        cx, cy, cz = org + (contact[0] + 0.5) * cs, org + (contact[1] + 0.5) * cs, org + (contact[2] + 0.5) * cs
        def dens_t(t):
            return self.trilerp_density(wi + t * dx_, wj + t * dy_, wk + t * dz_)
        lo = t_enter - 0.85 * cs
        hi = math.sqrt((cx - wi) ** 2 + (cy - wj) ** 2 + (cz - wk) ** 2)
        for _ in range(3):
            if dens_t(lo) >= DENS_ISO:
                lo -= cs
            else:
                break
        if dens_t(lo) >= DENS_ISO:
            # degenerate (started inside material): fall back to cell centre
            return (round(cx * FIX), round(cy * FIX), round(cz * FIX)), contact
        for _ in range(14):
            mid = (lo + hi) / 2
            if dens_t(mid) >= DENS_ISO:
                hi = mid
            else:
                lo = mid
        t = hi
        wx, wy, wz = wi + t * dx_, wj + t * dy_, wk + t * dz_
        return (round(wx * FIX), round(wy * FIX), round(wz * FIX)), contact

    def tap_ray(self, orig, d):
        t = time.perf_counter()
        hit = self.resolve_ray(orig, d)
        self.times["ray"] += time.perf_counter() - t
        if hit is None:
            self.s["rejected"] += 1
            return {"ok": False, "reason": "miss_rejected"}
        (hx, hy, hz), cell = hit
        self.impact(hx, hy, hz)
        self.s["taps"] += 1
        return {"ok": True, "hit": (hx, hy, hz), "hit_cell": cell}

    # ---------- damage ----------
    def impact(self, hx, hy, hz):
        """Apply one accepted tap at world fixed point (hx,hy,hz)."""
        t0 = time.perf_counter()
        L, cs, org = self.L, self.cs, self.origin
        wx, wy, wz = hx / FIX, hy / FIX, hz / FIX
        R = int(math.ceil(R_IMPACT))
        ci = int((wx - org) / cs); cj = int((wy - org) / cs); ck = int((wz - org) / cs)
        rb = int(math.ceil(R_BOND))
        removed_now = []
        rc = R_IMPACT * cs
        # density carving
        for i in range(ci - R, ci + R + 1):
            for j in range(cj - R, cj + R + 1):
                for k in range(ck - R, ck + R + 1):
                    cell = (i, j, k)
                    dcur = self.density.get(cell)
                    if dcur is None:
                        continue
                    ccx = org + (i + 0.5) * cs
                    ccy = org + (j + 0.5) * cs
                    ccz = org + (k + 0.5) * cs
                    dist = math.sqrt((ccx-wx)**2 + (ccy-wy)**2 + (ccz-wz)**2)
                    if dist > rc:
                        continue
                    fall = max(0.0, 1.0 - dist / rc)
                    wgt = fall * fall * (3 - 2 * fall)   # smoothstep kernel
                    hard = self.hardness(cell)
                    take = K_COMPRESS * wgt / hard
                    newd = dcur - take
                    # neighbouring voids make a cell easier to crumble (no lateral support)
                    if newd < DENS_FAIL:
                        removed_now.append(cell)
                    else:
                        self.density[cell] = int(round(newd))
                # (k loop closed above)
        # bond damage + fatigue
        for i in range(ci - rb, ci + rb + 1):
            for j in range(cj - rb, cj + rb + 1):
                for k in range(ck - rb, ck + rb + 1):
                    cell = (i, j, k)
                    if cell not in self.density:
                        continue
                    ccx = org + (i + 0.5) * cs
                    ccy = org + (j + 0.5) * cs
                    ccz = org + (k + 0.5) * cs
                    dist = math.sqrt((ccx-wx)**2 + (ccy-wy)**2 + (ccz-wz)**2)
                    rbw = R_BOND * cs
                    if dist > rbw:
                        continue
                    fall = max(0.0, 1.0 - dist / rbw)
                    wgt = fall * fall * (3 - 2 * fall)
                    vk = vkey(*cell, self.L)
                    self.fatigue[vk] = self.fatigue.get(vk, 0) + K_BOND * wgt * 0.05
                    to_add = K_BOND * wgt
                    for bkey, n in self.bonds_of(cell):
                        tough = (self.toughness(cell) + self.toughness(n)) * 0.5
                        cur = self.bdamage.get(bkey, 0)
                        flaw = cur > 0 or self._near_flaw(cell, n)
                        if not flaw:
                            continue    # pristine interior bond: elastic, no damage yet
                        dmg = cur + int(to_add / tough) + self._clamped_sc(bkey)
                        if dmg >= BOND_STRENGTH * tough:
                            self._sever(bkey)
                        else:
                            self.bdamage[bkey] = dmg
        # material actually crumbles (removal AFTER damage accumulation: order-
        # dependent by design; strictly sequential processing is required)
        for cell in removed_now:
            if cell in self.density:
                self.density.pop(cell)
                self.s["crumbles"] += 1
                # escaping material: what was left
                self.s["mass_removed"] += 1
        self._dirty_cells.update(removed_now)
        self.s["mass_applied"] += K_COMPRESS
        if self._sc_queue:
            self._drain_stress()
        self.times["impact"] += time.perf_counter() - t0
        return removed_now

    def _near_flaw(self, c, n=None):
        """A bond is only damageable once a flaw reaches it: an endpoint with
        reduced density, existing damage, or a severed sibling bond. This is
        what localises cracks instead of shredding the whole neighbourhood."""
        L = self.L
        i, j, k = c
        cells = [c] + ([n] if n else [])
        for cc in cells:
            d = self.density.get(cc)
            if d is not None and d < DENS_MAX - 8:
                return True
            if self.fatigue.get(vkey(*cc, L), 0) > 400:
                return True
            # is a sibling bond of cc already weakened or severed?
            for bkey, _n in self.bonds_of(cc):
                dm = self.bdamage.get(bkey, 0)
                if dm > 250:
                    return True
                if bkey in self.severed:
                    return True
                if dm == 0:
                    continue
        return False

    def _clamped_sc(self, bkey):
        return 0    # stress concentration added at sever time (see below)

    def _sever(self, bkey):
        """Sever one bond and queue stress concentration to sibling bonds of
        both endpoints (drives crack growth along localised paths). Iterative;
        the queue is drained by the caller with a per-impact bound."""
        self.severed.add(bkey)
        self.bdamage.pop(bkey, None)
        self.s["sev_total"] += 1
        self._sc_queue = getattr(self, "_sc_queue", [])
        self._sc_queue.append(bkey)

    def _drain_stress(self, budget=2000):
        """Deterministic bounded crack propagation: each severed bond stores
        stress into sibling bonds of its endpoints; siblings that now exceed
        their strength sever too and enqueue. Stops when the budget is spent
        or the queue empties. SC only enters bonds already near a flaw."""
        drained = 0
        while self._sc_queue and drained < budget:
            bkey = self._sc_queue.pop()
            drained += 1
            va, vb = bkey >> 24, bkey & 0xFFFFFF
            for v in (va, vb):
                c = vunkey(v, self.L)
                i, j, k = c
                va0 = vkey(*c, self.L)
                for dx, dy, dz in _NEIGH6:
                    n = (i+dx, j+dy, k+dz)
                    if n not in self.density:
                        continue
                    vb0 = vkey(*n, self.L)
                    bkey2 = (va0 << 24) | vb0 if va0 < vb0 else (vb0 << 24) | va0
                    if bkey2 == bkey or bkey2 in self.severed:
                        continue
                    # stress enters only bonds near a flaw (no leaps into
                    # pristine material)
                    if not self._near_flaw(c, n):
                        continue
                    self.bdamage[bkey2] = self.bdamage.get(bkey2, 0) + SC_PROP
                    tough = self.toughness(c) * 0.5 + self.toughness(n) * 0.5
                    if self.bdamage[bkey2] >= BOND_STRENGTH * tough:
                        self._sever(bkey2)
        self._sc_queue = []

    # ---------- connectivity / fragments ----------
    def components(self):
        """Connected components over solid cells joined by LIVE bonds (undirected:
        traverse all 6 neighbours with canonical bond keys). Full scan O(V)."""
        t0 = time.perf_counter()
        L = self.L
        seen = set()
        comps = []
        for start in sorted(self.density):
            if start in seen:
                continue
            comp = {start}
            seen.add(start)
            stack = [start]
            while stack:
                c = stack.pop()
                i, j, k = c
                va = vkey(*c, L)
                for dx, dy, dz in _NEIGH6:
                    n = (i+dx, j+dy, k+dz)
                    if n not in self.density or n in seen:
                        continue
                    vb = vkey(*n, L)
                    key = (va << 24) | vb if va < vb else (vb << 24) | va
                    if key in self.severed:
                        continue
                    seen.add(n)
                    comp.add(n)
                    stack.append(n)
            comps.append(comp)
        self.times["conn"] += time.perf_counter() - t0
        return comps

    def fragments(self):
        comps = self.components()
        if not comps:
            return comps[:1], []
        comps.sort(key=len, reverse=True)
        return comps[:1], comps[1:]

    def hash_state(self):
        import hashlib, struct as _s
        h = hashlib.sha256()
        for c in sorted(self.density):
            h.update(_s.pack("<i", self.density[c]) + _s.pack("<iii", *c))
        for b in sorted(self.severed):
            h.update(_s.pack("<Q", b))
        return h.hexdigest()[:24]
