"""DENT Stage 0.3 — engine (copy of s02_rock.py) with:
- DFIX fixed-point density option (Model A: sub-integer per-tap carve rates
  must not round to zero; density stored internally at DFIX units/legacy-unit).
- Per-instance damage scaling (self.alpha) applied to K_COMPRESS, K_BOND and
  fatigue accumulation, so calibration models can be compared in ONE engine.
- Removal attribution: every crumbled cell records (pre-tap density, take
  applied by the fatal tap) in self.attr for component-level depletion analysis.
- Optional severing disable (NOSEV) and fatigue-flaw disable (NOFAT) for
  counterfactual attribution runs.
With alpha=1, DFIX=1, both flags on, behaviour is identical to s02_rock.py.

Original Stage 0.2 docstring follows.
DENT Stage 0.2 — density-field sparse voxel rock with bond-lattice fracture.

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

DFIX = 1                # fixed-point density multiplier; 1 = legacy integer.
                        # Stage 0.3 Model A uses DFIX=65536 (phase-locked to
                        # the contract-v3 world fixed point).


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
    def __init__(self, verts, tris, lattice=96, cover_iters=3,
                 alpha=1.0, dfix=None, no_sev=False, no_fat_flaw=False,
                 cap_mass=None, beta=0.0, support=False, grain=False):
        self.L = lattice
        self.origin = -1.05
        self.span = 2.10
        self.cs = self.span / self.L
        self.mat = MaterialField()
        # Stage 0.3 per-instance configuration:
        self.alpha = float(alpha)        # damage-constant scale (Model A et al.)
        self.dfix = int(dfix) if dfix else DFIX   # density units per legacy unit
        self.no_sev = bool(no_sev)       # counterfactual: bonds never sever
        self.no_fat_flaw = bool(no_fat_flaw)  # counterfactual: fatigue never opens flaws
        # Model A/B mass cap: maximum total carve (legacy density units) any
        # single accepted tap may remove across its whole kernel. With
        # cap_mass = capacity/1e9 the rock CANNOT fully deplete before 1e9
        # accepted taps (per-tap mass is bounded; crumble jump adds <= 30
        # units/cell once -> stated as a derived bound with a measured margin).
        self.cap_mass = cap_mass
        # Model B: local-fatigue softening of INDENTATION resistance.
        # hard_eff = hard / (1 + beta * fatigue/400); concentrated taps
        # accelerate only the spot they actually work (spatially exact),
        # under the same cap -> cannot violate the no-early-death bound.
        self.beta = float(beta)
        # Model C: structural support coherence. Erosion resistance scales
        # with live lateral support (n_solid 6-neighbours -> factor
        # 0.55 + 0.075*n, i.e. x0.55 for a lone cell, x1.0 fully embedded).
        # Only touches cells that are actually being eroded.
        self.support = bool(support)
        # Grain structure (natural-fracture aid): the material is composed of
        # grains (region ids from integer noise); inter-granular bonds are
        # weaker (0.72..0.85), so cracks preferentially follow grain
        # boundaries and can CLOSE LOOPS -> multi-cell natural fragments.
        # Purely a material property; no geometry is prescribed anywhere.
        self.grain = bool(grain); self.grain_size = 9.0; self.grain_seed = 911
        self.attr = dict(removals=0, single_tap_kills=0,
                         pre_death_bucket=[0]*8, take_sum=0.0,
                         fatal_takes=[], first_removal_tap=None,
                         first_sub120_tap=None, first_sub200_tap=None)
        self.density = {}            # (i,j,k) -> int density in DFIX units (sparse)
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
                        d = int(round(DENS_MAX * m)) * self.dfix
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
                    avg = (ssum / solid_n) / self.dfix if solid_n else 0
                    f = 0.5 + 0.18 * it   # relax: 0.5,0.68,0.86
                    target = (cur / self.dfix) * f + avg * (1 - f) if solid_n else 0
                    new[c] = max(8, int(round(target * ((cur / self.dfix) / DENS_MAX) ** 0.25))) * self.dfix
                else:
                    new[c] = cur
            self.density = new
            cells = sorted(self.density)
        # crumble any now-invalid cells
        dead = [c for c, d in self.density.items() if d // self.dfix < DENS_FAIL]
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

    def grain_id(self, c):
        """Deterministic grain region id for a cell (integer-noise Voronoi)."""
        gs = self.grain_size
        return (int(c[0] // gs) * 73856093, int(c[1] // gs) * 19349663, int(c[2] // gs) * 83492791)

    def grain_factor(self, c, n):
        """Bond toughness multiplier: 1.0 intra-granular, 0.72..0.85 across
        a grain boundary (deterministic per bond)."""
        if not self.grain:
            return 1.0
        ga, gb = self.grain_id(c), self.grain_id(n)
        if ga == gb:
            return 1.0
        h = ((ga[0] ^ ga[1]) * 2654435761 ^ (gb[1] ^ gb[2]) * 40503) & 0xFFFF
        return 0.72 + 0.13 * (h / 65535.0)

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
        return acc / self.dfix    # trilerp always speaks legacy units (0..240)

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
        """Apply one accepted tap at world fixed point (hx,hy,hz).
        Stage 0.3: alpha-scaled, fixed-point densities, removal attribution.
        cap_mass: with the cap enabled the carve becomes a two-pass pass
        (collect takes, scale to the cap, apply); without it the legacy
        single-pass flow is preserved bit-exactly."""
        t0 = time.perf_counter()
        L, cs, org = self.L, self.cs, self.origin
        A = self.alpha
        wx, wy, wz = hx / FIX, hy / FIX, hz / FIX
        R = int(math.ceil(R_IMPACT))
        ci = int((wx - org) / cs); cj = int((wy - org) / cs); ck = int((wz - org) / cs)
        cap_flag = self.cap_mass is not None
        rb = int(math.ceil(R_BOND))
        removed_now = []
        rc = R_IMPACT * cs
        # density carving
        takes = [] if self.cap_mass else None
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
                    if self.beta:
                        fat = self.fatigue.get(vkey(*cell, self.L), 0)
                        hard = hard / (1.0 + self.beta * fat / 400.0)
                    if self.support:
                        ns = 0
                        for ddx, ddy, ddz in _NEIGH6:
                            if (cell[0]+ddx, cell[1]+ddy, cell[2]+ddz) in self.density:
                                ns += 1
                        hard = hard * (0.55 + 0.075 * ns)
                    # Stage 0.3: carve in legacy units, then to fixed point.
                    # take*A stays float here; only the STORED value is integer
                    # fixed point, so sub-1-unit takes accumulate losslessly
                    # down to 1/DFIX of a legacy density unit.
                    take = A * K_COMPRESS * wgt / hard
                    if cap_flag:
                        takes.append((cell, take, dcur))
                        continue
                    newd = dcur - take * self.dfix
                    # neighbouring voids make a cell easier to crumble (no lateral support)
                    if newd < DENS_FAIL * self.dfix:
                        removed_now.append(cell)
                        # ---- Stage 0.3 attribution ----
                        a = self.attr
                        a["removals"] += 1
                        d0l = dcur / self.dfix
                        a["take_sum"] += take
                        if take >= d0l - DENS_FAIL:
                            a["single_tap_kills"] += 1
                        b = min(7, int(d0l / 30))
                        a["pre_death_bucket"][b] += 1
                        if len(a["fatal_takes"]) < 20000:
                            a["fatal_takes"].append((round(d0l, 3), round(take, 4)))
                        if a["first_removal_tap"] is None:
                            a["first_removal_tap"] = self.s["taps"] + 1
                    else:
                        self.density[cell] = int(round(newd))
                        dl = newd / self.dfix
                        if dl < 120 and self.attr["first_sub120_tap"] is None:
                            self.attr["first_sub120_tap"] = self.s["taps"] + 1
                        if dl < 200 and self.attr["first_sub200_tap"] is None:
                            self.attr["first_sub200_tap"] = self.s["taps"] + 1
                # (k loop closed above)
        if cap_flag:
            self._apply_carves(takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc, removed_now)
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
                    self.fatigue[vk] = self.fatigue.get(vk, 0) + A * K_BOND * wgt * 0.05
                    to_add = A * K_BOND * wgt
                    for bkey, n in self.bonds_of(cell):
                        tough = (self.toughness(cell) + self.toughness(n)) * 0.5 * self.grain_factor(cell, n)
                        if self.no_sev:
                            tough = 1e18   # counterfactual: bonds cannot sever
                        cur = self.bdamage.get(bkey, 0)
                        flaw = cur > 0 or self._near_flaw(cell, n)
                        if not flaw:
                            continue    # pristine interior bond: elastic, no damage yet
                        if self.alpha == 1.0 and self.dfix == 1:
                            # legacy exact path (Stage 0.2 byte-parity)
                            dmg = cur + int(to_add / tough) + self._clamped_sc(bkey)
                        else:
                            # Stage 0.3: bond damage kept as a FLOAT in legacy
                            # units so alpha-scaled takes accumulate losslessly
                            # (int() truncation would swallow alpha*K_BOND).
                            dmg = cur + to_add / tough + self._clamped_sc(bkey) * A
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
        for cell in removed_now[:0]:
            pass
        self._dirty_cells.update(removed_now)
        self.s["mass_applied"] += K_COMPRESS
        if self._sc_queue:
            self._drain_stress()
        self.times["impact"] += time.perf_counter() - t0
        return removed_now

    def _apply_carves(self, takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc, removed_now):
        """Two-pass carve used ONLY when cap_mass is set (Model A/B).
        takes: list of (cell, take, dcur). Scales all takes uniformly if the
        kernel total exceeds the cap, then applies. Deterministic."""
        total = sum(t for _, t, _ in takes)
        f = min(1.0, self.cap_mass / total) if (self.cap_mass and total > 0) else 1.0
        for cell, take, dcur in takes:
            tf = take * f * self.dfix
            newd = dcur - tf
            if newd < DENS_FAIL * self.dfix:
                removed_now.append(cell)
                a = self.attr
                a["removals"] += 1
                d0l = dcur / self.dfix
                a["take_sum"] += take * f
                if take * f >= d0l - DENS_FAIL:
                    a["single_tap_kills"] += 1
                b = min(7, int(d0l / 30))
                a["pre_death_bucket"][b] += 1
                if len(a["fatal_takes"]) < 20000:
                    a["fatal_takes"].append((round(d0l, 3), round(take * f, 4)))
                if a["first_removal_tap"] is None:
                    a["first_removal_tap"] = self.s["taps"] + 1
            else:
                self.density[cell] = int(round(newd))

    def _near_flaw(self, c, n=None):
        """A bond is only damageable once a flaw reaches it: an endpoint with
        reduced density, existing damage, or a severed sibling bond. This is
        what localises cracks instead of shredding the whole neighbourhood."""
        L = self.L
        i, j, k = c
        cells = [c] + ([n] if n else [])
        for cc in cells:
            d = self.density.get(cc)
            if d is not None and d // self.dfix < DENS_MAX - 8:
                return True
            if not self.no_fat_flaw and self.fatigue.get(vkey(*cc, L), 0) > 400:
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
                    # Stage 0.3: stress concentration is also alpha-scaled
                    # (it is per-sever damage, not a threshold).
                    sc = SC_PROP * self.alpha if (self.alpha != 1.0 or self.dfix > 1) else SC_PROP
                    self.bdamage[bkey2] = self.bdamage.get(bkey2, 0) + sc
                    if self.alpha != 1.0:
                        self.bdamage[bkey2] = float(self.bdamage[bkey2])
                    tough = (self.toughness(c) * 0.5 + self.toughness(n) * 0.5) * self.grain_factor(c, n)
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
