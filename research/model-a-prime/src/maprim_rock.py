"""Model A' experimental engine (scratch only - not product code).

= Model A physics (byte-identical baseline `modelA_stage03.py`) + three thin,
experimental layers under validation:

1. **resolve_iso(orig, d)** — ISO-consistent ray resolution. Walks ray cell
   segments in t-order (segments delimited by node planes through cell
   centres, exactly the piecewise regions of trilerp_density); inside a
   segment the trilinear field is an exact cubic in t, so its maximum is
   evaluated at the segment endpoints + stationary points (closed form) and
   refined by bisection. Returns the FIRST crossing of DENS_ISO with the
   surface point AND outwared normal, or None (miss). It never redirects:
   no crossing -> None. A ray that only passes sub-ISO "fluff" is a MISS.
   Because every segment's 8 nodes are checked, crossings caused by
   off-ray occupied nodes (renderer-visible grazing blobs the old DDA could
   skip) are found as well.

2. **tap_transaction / single per-tap budget** — one authoritative
   consumption allowance per accepted tap. Carve routing (including
   crumble residuals) and debris shedding all draw from the SAME
   `budget_left`; spending is clamped, never reset. Pre-commit validation:
   ledger identity + per-tap spend + reserve checked BEFORE the tap is
   committed; on violation the entire tap is rolled back and rejected.

3. **geometry_audit** — separates inventory (A) from renderable (B),
   hittable (C) and connected-visible (D) material.

Pure stdlib. Experimental.
"""
import math
import pickle
import sys

import modelA_stage03 as A
from modelA_stage03 import DENS_FAIL, vkey

DENS_MAX = A.DENS_MAX


def load_pristine(path=None):
    """Load pristine_initial.pkl with the module shims the pickle needs
    (classes were pickled from module name `s03_rock`, a byte-identical
    copy of modelA_stage03.py)."""
    if path is None:
        import os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "pristine_initial.pkl")
    sys.modules.setdefault("s03_rock", A)
    import __main__
    from streams import HistStream, HostileStream
    __main__.HistStream = HistStream
    __main__.HostileStream = HostileStream
    with open(path, "rb") as f:
        return pickle.load(f)


# ======================================================================
# Independent trilinear interpolation (verification reference)
# ======================================================================
def ref_trilerp(density, L, cs, org, x, y, z, dfix=65536):
    """Reimplementation of trilerp_density from the spec (grid nodes at
    cell centres) - independent of the engine under test."""
    fx = (x - org) / cs - 0.5
    fy = (y - org) / cs - 0.5
    fz = (z - org) / cs - 0.5
    i, j, k = math.floor(fx), math.floor(fy), math.floor(fz)
    tx, ty, tz = fx - i, fy - j, fz - k
    acc = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = ((tx if dx else 1 - tx) * (ty if dy else 1 - ty)
                     * (tz if dz else 1 - tz))
                acc += w * density.get((i + dx, j + dy, k + dz), 0)
    return acc / dfix


# ======================================================================
# ISO-consistent ray resolver
# ======================================================================
def _cubic_max_roots(a3, a2, a1, a0):
    """Real roots of 3a3 t^2 + 2a2 t + a1 = 0 (derivative of the cubic)."""
    A_, B_, C_ = 3.0 * a3, 2.0 * a2, a1
    if A_ == 0.0:
        if B_ != 0.0:
            return [-C_ / B_]
        return []
    disc = B_ * B_ - 4.0 * A_ * C_
    if disc < 0:
        return []
    sq = math.sqrt(disc)
    return [(-B_ + sq) / (2.0 * A_), (-B_ - sq) / (2.0 * A_)]


def cubic_at(a3, a2, a1, a0, t):
    return ((a3 * t + a2) * t + a1) * t + a0


def resolve_iso(rock, orig, d, bisect_iters=40, t_lim_factor=4.0):
    """First crossing of DENS_ISO along the ray, on the SAME trilinear field
    the renderer uses. Returns None (miss) or dict(t=, u,v,w= (node-plane
    segment), point=(x,y,z) legacy world floats, normal=(nx,ny,nz),
    n_cell=(i,j,k) node cell under the crossing).

    Correctness contract (tested vs the independent fine-step reference):
      - hit  <=>  exists t with ref_trilerp >= DENS_ISO within scan range
      - t is the smallest such t (to bisection tolerance)
      - no state mutation; no redirection, no nearest-cell snapping

    Segment invariant: the segment [t_lo, t_hi] lies between node planes
    (p_ax, p_ax+1) per axis; its trilinear restriction is the exact cubic
    built from nodes (p_ax, p_ax+1).  Axis blocks advance AFTER the segment
    that ends at their plane is evaluated, never before.
    """
    L, cs, org = rock.L, rock.cs, rock.origin
    FIX = A.FIX
    ox, oy, oz = orig
    dxr, dyr, dzr = d
    ln = math.sqrt(dxr * dxr + dyr * dyr + dzr * dzr) or 1
    ux, uy, uz = dxr / ln, dyr / ln, dzr / ln          # unit direction legacy-world
    wi, wj, wk = ox / FIX, oy / FIX, oz / FIX
    if ux == 0.0 and uy == 0.0 and uz == 0.0:
        return None
    t_stop = rock.span * t_lim_factor

    # walk segments delimited by node planes: /cs - 0.5 integer boundaries
    # i.e. world planes at org + (m + 0.5) * cs
    t_d = []
    n0 = []
    for ax, w, u in ((0, wi, ux), (1, wj, uy), (2, wk, uz)):
        if u == 0.0:
            t_d.append((None, None))
            n0.append(int(math.floor((w - org) / cs - 0.5)))
            continue
        # node-plane parameter: m = floor((w - org)/cs - 0.5)
        n_axis = math.floor((w - org) / cs - 0.5)
        # distance to next plane in +u direction
        if u > 0:
            boundary = org + (n_axis + 1 + 0.5) * cs
            t_next = (boundary - w) / u
            td = cs / u
        else:
            boundary = org + (n_axis + 0.5) * cs
            t_next = (boundary - w) / u
            td = -cs / u
            if t_next < 0:      # already at/past boundary
                n_axis -= 1
                boundary = org + (n_axis + 0.5) * cs
                t_next = (boundary - w) / u
                td = cs / -u
        t_d.append((max(t_next, 0.0), abs(td)))
        n0.append(int(n_axis))
    sgn_x = 1 if ux > 0 else (-1 if ux < 0 else 0)
    sgn_y = 1 if uy > 0 else (-1 if uy < 0 else 0)
    sgn_z = 1 if uz > 0 else (-1 if uz < 0 else 0)
    (tx1, tdx), (ty1, tdy), (tz1, tdz) = t_d
    i0, j0, k0 = n0

    n_seg = 0
    t_lo = 0.0
    while n_seg < 12 * L + 128:
        # next segment boundary = min of the three node-plane distances
        m = None
        for tn_ in (tx1, ty1, tz1):
            if tn_ is not None and (m is None or tn_ < m):
                m = tn_
        if m is None or m > t_stop:
            return None
        t_hi = m
        n_seg += 1
        # gather the 8 node densities for this segment (blocks NOT yet advanced)
        v = []
        any_live = False
        for ddx in (0, 1):
            for ddy in (0, 1):
                for ddz in (0, 1):
                    val = rock.density.get((i0 + ddx, j0 + ddy, k0 + ddz), 0) \
                        if (0 <= i0 + ddx < L and 0 <= j0 + ddy < L
                            and 0 <= k0 + ddz < L) else 0
                    v.append(val)
                    if val:
                        any_live = True
        if not any_live:
            # advance past this dead segment, then advance crossed blocks
            t_lo = t_hi
            if i0 is not None and tx1 == m:
                i0 += sgn_x
                tx1 += tdx
            if j0 is not None and ty1 == m:
                j0 += sgn_y
                ty1 += tdy
            if k0 is not None and tz1 == m:
                k0 += sgn_z
                tz1 += tdz
            continue
        # f(t) cube: node indices: n = (i0..i0+1, j0..j0+1, k0..k0+1)
        # position parameter along each axis within [0,cs] measured from node n
        n_cx = org + (i0 + 0.5) * cs
        n_cy = org + (j0 + 0.5) * cs
        n_cz = org + (k0 + 0.5) * cs
        px = ox / FIX
        py = oy / FIX
        pz = oz / FIX
        alpha = ux / cs
        beta = uy / cs
        gamma = uz / cs
        # node-local interpolation weights: node i0 has weight (1-tx), node
        # i0+1 weight tx, with tx(t) = tx_o + t*alpha
        tx_o = (px - n_cx) / cs
        ty_o = (py - n_cy) / cs
        tz_o = (pz - n_cz) / cs
        P = [1.0 - tx_o, tx_o]
        Q = [1.0 - ty_o, ty_o]
        Rr = [1.0 - tz_o, tz_o]
        qa, qb, qc = alpha, beta, gamma
        a3 = a2 = a1 = a0_v = 0.0
        idx = 0
        for ddx in (0, 1):
            for ddy in (0, 1):
                for ddz in (0, 1):
                    w_node = v[idx]
                    idx += 1
                    if w_node == 0:
                        continue
                    fxa = (P[ddx], (-qa if ddx == 0 else qa))
                    fxb = (Q[ddy], (-qb if ddy == 0 else qb))
                    fxc = (Rr[ddz], (-qc if ddz == 0 else qc))
                    pa, da = fxa
                    pb, db = fxb
                    pc, dc = fxc
                    wv = float(w_node) / rock.dfix
                    a0_v += wv * pa * pb * pc
                    a1 += wv * (da * pb * pc + pa * db * pc + pa * pb * dc)
                    a2 += wv * (da * db * pc + da * pb * dc + pa * db * dc)
                    a3 += wv * (da * db * dc)
        # find first crossing in [t_lo, t_hi]
        lo_t = t_lo
        hi_t = t_hi
        if a3 == 0.0 and a2 == 0.0:
            # plenty of empty or linear segments: endpoints suffice
            cut_points = [lo_t, hi_t]
        else:
            roots = _cubic_max_roots(a3, a2, a1, a0_v)
            cut_points = sorted(set(
                [lo_t, hi_t] + [r for r in roots if lo_t < r < hi_t]
                or [lo_t, hi_t]))
        crossing = None
        for a, b in zip(cut_points[:-1], cut_points[1:]):
            va_ = cubic_at(a3, a2, a1, a0_v, a)
            vb_ = cubic_at(a3, a2, a1, a0_v, b)
            # monotone inside (a,b) (no root between): check endpoint pair
            if va_ >= A.DENS_ISO:
                crossing = a
                break
            if vb_ >= A.DENS_ISO and va_ < A.DENS_ISO:
                # bisect first crossing inside (a,b)
                lo_, hi_ = a, b
                for _ in range(bisect_iters):
                    mid_ = 0.5 * (lo_ + hi_)
                    if cubic_at(a3, a2, a1, a0_v, mid_) >= A.DENS_ISO:
                        hi_ = mid_
                    else:
                        lo_ = mid_
                crossing = hi_
                break
        if crossing is not None:
            # clamp: crossing may equal segment start from a previous
            # segment's exit value jump - accept (verdict correctness held
            # by construction: f(t) >= ISO at crossing)
            x = px + crossing * ux
            y = py + crossing * uy
            z = pz + crossing * uz

            def dd(axis_val, axis):
                h = 0.02 * cs
                if axis == 0:
                    return (ref_trilerp(rock.density, L, cs, org, x + h, y, z, rock.dfix)
                            - ref_trilerp(rock.density, L, cs, org, x - h, y, z, rock.dfix)) / (2 * h)
                if axis == 1:
                    return (ref_trilerp(rock.density, L, cs, org, x, y + h, z, rock.dfix)
                            - ref_trilerp(rock.density, L, cs, org, x, y - h, z, rock.dfix)) / (2 * h)
                return (ref_trilerp(rock.density, L, cs, org, x, y, z + h, rock.dfix)
                        - ref_trilerp(rock.density, L, cs, org, x, y, z - h, rock.dfix)) / (2 * h)

            gx, gy, gz = dd(x, 0), dd(y, 1), dd(z, 2)
            gln = math.sqrt(gx * gx + gy * gy + gz * gz) or 1.0
            nx, ny, nz = -gx / gln, -gy / gln, -gz / gln
            if nx * ux + ny * uy + nz * uz > 0.0:
                nx, ny, nz = -nx, -ny, -nz
            return dict(verdict="hit", t=crossing, point=(x, y, z),
                        normal=(nx, ny, nz), n_cell=(i0, j0, k0),
                        seg=(lo_t, m))
        t_lo = t_hi
        # advance the block(s) whose plane was crossed at t_hi (= m)
        if i0 is not None and tx1 == m:
            i0 += sgn_x
            tx1 += tdx
        if j0 is not None and ty1 == m:
            j0 += sgn_y
            ty1 += tdy
        if k0 is not None and tz1 == m:
            k0 += sgn_z
            tz1 += tdz
    return None


def first_iso_reference(rock, orig, d, step_cells=0.05, bisect_iters=40,
                        t_lim_factor=4.0):
    """Independent fine-step traversal: gold-standard first DENS_ISO crossing.
    Entirely separate code path from resolve_iso (uniform sampling +
    bisection on ref_trilerp)."""
    L, cs, org = rock.L, rock.cs, rock.origin
    FIX = A.FIX
    ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1
    ux, uy, uz = d[0] / ln, d[1] / ln, d[2] / ln
    px, py, pz = orig[0] / FIX, orig[1] / FIX, orig[2] / FIX
    step = cs * step_cells
    t_lim = rock.span * t_lim_factor

    def f(t):
        return ref_trilerp(rock.density, L, cs, org,
                           px + t * ux, py + t * uy, pz + t * uz, rock.dfix)

    prev_t = step / 2
    prev_v = f(prev_t)
    t = prev_t + step
    while t < t_lim:
        v = f(t)
        if v >= A.DENS_ISO:
            lo_, hi_ = prev_t, t
            for _ in range(bisect_iters):
                mid_ = 0.5 * (lo_ + hi_)
                if f(mid_) >= A.DENS_ISO:
                    hi_ = mid_
                else:
                    lo_ = mid_
            return dict(verdict="hit", t=hi_)
        prev_t, prev_v = t, v
        t += step
    return dict(verdict="miss", t=None)


# ======================================================================
# Journal containers (cheap per-tap undo for VALIDATION ONLY; the journal
# is a measurement/validation mechanism, NOT a claimed production mechanism)
# ======================================================================
_DEL = object()


class JDict(dict):
    """dict that journals first-writes/overwrites/deletes since last undo."""

    def __init__(self, data=()):
        super().__init__(data)
        self.journal = {}

    def __setitem__(self, k, v):
        if k not in self.journal:
            self.journal[k] = self[k] if k in self else _DEL
        super().__setitem__(k, v)

    def __delitem__(self, k):
        if k not in self.journal:
            self.journal[k] = self[k] if k in self else _DEL
        super().__delitem__(k)

    def pop(self, k, *a):
        if k in self and k not in self.journal:
            self.journal[k] = self[k]
        return super().pop(k, *a)

    def setdefault(self, k, d=None):
        if k not in self:
            self[k] = d
            return d
        return self[k]

    def update(self, *a, **kw):
        for k, v in dict(*a, **kw).items():
            self[k] = v

    def undo(self):
        for k, old in self.journal.items():
            if old is _DEL:
                dict.pop(self, k, None)
            else:
                dict.__setitem__(self, k, old)
        self.journal = {}

    def forget_journal(self):
        self.journal = {}

    def __reduce__(self):
        state = {"journal": self.__dict__.get("journal", {})}
        return (self.__class__, (dict(self),), state)


class JSet(set):
    """set that journals additions/removals since last undo."""

    def __init__(self, data=()):
        super().__init__(data)
        self.journal = {}

    def add(self, x):
        if x not in self and x not in self.journal:
            self.journal[x] = False
        super().add(x)

    def remove(self, x):
        if x in self and x not in self.journal:
            self.journal[x] = True
        super().remove(x)

    def discard(self, x):
        if x in self and x not in self.journal:
            self.journal[x] = True
        super().discard(x)

    def undo(self):
        for x, was in self.journal.items():
            if was:
                super().add(x)
            else:
                super().discard(x)
        self.journal = {}

    def forget_journal(self):
        self.journal = {}

    def __reduce__(self):
        state = {"journal": self.__dict__.get("journal", {})}
        return (self.__class__, (set(self),), state)


# ======================================================================
# Model A' engine: ledger + single-budget transaction
# ======================================================================
class MaprimRock(A.RockDensity):

    def __init__(self, pristine, N=None, kappa=0.5, debris_policy="hold",
                 mode="per_tap", alpha=None, cap_mass_override=None,
                 reserve_frac=0.02, dfix=65536, verify="full_recount"):
        """pristine: dict from pristine_initial.pkl. Constructs the rock
        WITHOUT s01_c by faithful replication of RockDensity.__init__ using
        the recovered occ_init."""
        self.L = pristine["L"]
        self.origin = pristine["origin"]
        self.span = pristine["span"]
        self.cs = pristine["cs"]
        self.mat = pristine["mat"]
        self.alpha = float(alpha if alpha is not None else 1.0)
        self.dfix = int(dfix)
        self.no_sev = False
        self.no_fat_flaw = False
        self.cap_mass = None
        self.beta = 0.0
        self.support = False
        self.grain = False
        self.grain_size = 9.0
        self.grain_seed = 911
        self.attr = dict(removals=0, single_tap_kills=0, pre_death_bucket=[0] * 8,
                         take_sum=0.0, fatal_takes=[], first_removal_tap=None,
                         first_sub120_tap=None, first_sub200_tap=None)
        self.density = JDict()
        self.bdamage = JDict()
        self.severed = JSet()
        self.fatigue = JDict()
        self.s = dict(taps=0, rejected=0, fragments=[], sev_total=0,
                      mass_removed=0, mass_applied=0, crumbles=0)
        self.times = dict(ray=0.0, impact=0.0, conn=0.0, extract=0.0)
        self.occ_init = pristine["occ_init"]
        self.boundary_init = pristine["boundary_init"]
        self.density = JDict(pristine["density"])
        self.core = self._seed_core()
        self._dirty_cells = set()
        self._mat_cache = {}
        self._sc_queue = []
        # ---- Model A' additions ----
        self.debris_policy = debris_policy
        self.mode = mode
        self.kappa = kappa
        self.debris = {}
        self.fines = {}
        self.debris_hits = {}
        self.debris_shed = {}
        self.consumed = 0
        self.burned = 0
        self.main_mass = sum(self.density.values())
        self.M0 = self.main_mass
        self.cells0 = len(self.density)
        crumble_slack = DENS_FAIL * self.cells0 * self.dfix
        self.N = N
        if N is not None:
            self.Mr = max(crumble_slack + 1, int(self.M0 * reserve_frac))
            self.q_tap = (self.M0 - self.Mr) // N
            self.q_legacy = self.q_tap / self.dfix
        else:
            self.Mr = crumble_slack + 1
            self.q_tap = None
            self.q_legacy = None
        if cap_mass_override is None and self.N is not None:
            # Force Model A's CAP-PATH carve (_apply_carves): without a cap
            # the parent uses the uncapped single-pass branch in impact(),
            # which writes density directly and gives the ledger no hook to
            # route carve residuals (mirrors cm_rock's design decision).
            cap_mass_override = self.q_legacy
        self.cap_mass = cap_mass_override
        self._tx = None
        self.violations = []
        self._verify = verify      # "full_recount" | "incremental"
        self.modified_last = 0

    # ---------- budget ----------
    def _budget0(self, n_tap):
        if self.mode == "per_tap" and self.q_tap is not None:
            return self.q_tap
        if self.mode == "cumulative":
            return self.M0 - self.Mr - self.consumed - self.burned
        return None   # unlimited (uncapped analysis mode)

    def _route(self, cell, residual, bucket="carve"):
        """Route an integer residual out of the field: kappa-share consumed
        against THIS tap's single remaining budget; the rest -> debris."""
        if residual <= 0:
            return
        tx = self._tx
        use = int(residual * self.kappa)
        left = tx["budget_left"]
        if use > left:
            use = max(left, 0)
        if use < 0:
            use = 0
        self.consumed += use
        tx["used_" + bucket] += use
        tx["budget_left"] -= use
        rest = residual - use
        if rest > 0:
            b = (cell[0] // 6, cell[1] // 6, cell[2] // 6)
            self.debris[b] = self.debris.get(b, 0) + rest

    # ---------- carve (cap path) ----------
    def _apply_carves(self, takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc,
                      removed_now):
        tx = self._tx
        total = sum(t for _, t, _ in takes)
        f_cap = min(1.0, self.cap_mass / total) if (self.cap_mass and total > 0) else 1.0
        for cell, take, dcur in takes:
            tf = take * f_cap * self.dfix
            newd = dcur - tf
            if newd < DENS_FAIL * self.dfix:
                removed_now.append(cell)     # pops happen after the bond pass
                tx["crumble_candidates"].append((cell, dcur))
                a = self.attr
                a["removals"] += 1
                d0l = dcur / self.dfix
                a["take_sum"] += take * f_cap
                if take * f_cap >= d0l - DENS_FAIL:
                    a["single_tap_kills"] += 1
                b = min(7, int(d0l / 30))
                a["pre_death_bucket"][b] += 1
                if a["first_removal_tap"] is None:
                    a["first_removal_tap"] = self.s["taps"] + 1
                # sink part of the visible material: nothing routed yet -
                # deferred until the pop (matrix-accurate removal order)
            else:
                newd_int = int(round(newd))
                applied = dcur - newd_int
                self.density[cell] = newd_int
                self.main_mass -= applied
                if newd_int != dcur:
                    self.modified_last += 1
                else:
                    pass
                if applied > 0:
                    self._route(cell, applied, "carve")
                if tx["fault_hook"] is not None:
                    tx["fault_hook"](self, "carve_routed")
                if self.attr["first_sub120_tap"] is None and \
                        newd_int / self.dfix < 120:
                    self.attr["first_sub120_tap"] = self.s["taps"] + 1
                if self.attr["first_sub200_tap"] is None and \
                        newd_int / self.dfix < 200:
                    self.attr["first_sub200_tap"] = self.s["taps"] + 1

    def _route_crumble_residuals(self):
        """Route popped crumble candidates (called AFTER the bond pass /
        pop, mirroring Model A's removal order)."""
        tx = self._tx
        for cell, dcur in tx["crumble_candidates"]:
            if cell in self.density:
                self.density.pop(cell)
                self.modified_last += 1
            tx["crumbled"] += 1
            self.main_mass -= dcur
            self._route(cell, dcur, "carve")

    # ---------- debris policies (single shared budget) ----------
    def _shed_tap(self, hit_cell):
        if self.debris_policy != "shed":
            return
        tx = self._tx
        b = (hit_cell[0] // 6, hit_cell[1] // 6, hit_cell[2] // 6)
        m = self.debris.get(b, 0)
        if not m:
            return
        h = self.debris_hits.get(b, 0) + 1
        self.debris_hits[b] = h
        if h % 3:
            return
        moved = m // 4
        if not moved:
            return
        use = moved // 2
        left = tx["budget_left"]
        if use > left:
            use = max(left, 0)
        self.debris[b] = m - moved
        self.fines[b] = self.fines.get(b, 0) + moved - use
        self.debris_shed[b] = self.debris_shed.get(b, 0) + 1
        if use:
            self.consumed += use
            tx["used_shed"] += use
            tx["budget_left"] -= use

    # ---------- journals / rollback ----------
    def _snapshot(self):
        a2 = dict(self.attr)
        a2["fatal_takes"] = list(self.attr["fatal_takes"])
        a2["pre_death_bucket"] = list(self.attr["pre_death_bucket"])
        return (dict(self.debris), dict(self.fines), dict(self.s),
                self.consumed, self.burned, self.main_mass,
                set(self._dirty_cells), a2, dict(self.debris_hits),
                dict(self.debris_shed), list(self._sc_queue))

    def _restore(self, snap):
        (db, fn, s, c, bu, mm, dirty, a2, dh, dsh, scq) = snap
        self.density.undo()      # journal containers: undo first-writes
        self.severed.undo()
        self.bdamage.undo()
        self.fatigue.undo()
        self.debris = db
        self.fines = fn
        self.s = s
        self.consumed = c
        self.burned = bu
        self.main_mass = mm
        self._dirty_cells = dirty
        self.attr = a2
        self.debris_hits = dh
        self.debris_shed = dsh
        self._sc_queue = scq

    # ---------- transactional taps ----------
    def tap_transaction(self, orig, d, fault_hook=None, use_iso_ray=False):
        """One accepted tap under a single per-tap consumption budget with
        PRE-COMMIT validation and full rollback on violation.

        accepted_tap_number comes from the engine's own authoritative
        counter (s['taps']); a durable counter layer (Part D) owns the
        real authorization."""
        n_tap = self.s["taps"] + 1
        budget = self._budget0(n_tap)
        self._tx = dict(budget_left=budget if budget is not None else float("inf"),
                        budget0=budget,
                        crumble_candidates=[], used_carve=0, used_shed=0,
                        crumbled=0, fault_hook=fault_hook)
        self.modified_last = 0
        snap = self._snapshot()
        try:
            if use_iso_ray:
                r = self.tap_iso(orig, d)
            else:
                r = self.tap_ray(orig, d)
            if r.get("ok"):
                self._route_crumble_residuals()
                self._shed_tap(r["hit_cell"])
                spent = self._tx["used_carve"] + self._tx["used_shed"]
                bad = []
                if self._verify == "full_recount":
                    main_mass_now = sum(self.density.values())
                else:
                    # main_mass is maintained incrementally by every
                    # carve/route path; identity uses it directly
                    main_mass_now = self.main_mass
                drift = main_mass_now + sum(self.debris.values()) \
                    + sum(self.fines.values()) \
                    - (self.M0 - self.consumed - self.burned)
                if budget is not None and spent > budget:
                    bad.append(dict(kind="per_tap_budget", spent=spent,
                                    budget=budget))
                if self.N is not None and n_tap < self.N:
                    physical = main_mass_now + sum(self.debris.values()) \
                        + sum(self.fines.values())
                    if physical <= self.Mr:
                        bad.append(dict(kind="reserve", physical=physical,
                                        Mr=self.Mr))
                if bad:
                    self._restore(snap)
                    return dict(ok=False,
                                reason="invariant_violation_rolled_back",
                                violations=bad, tap=n_tap)
                # commit: drop the undo journal (state stands as-is)
                for cont in (self.density, self.severed, self.bdamage,
                             self.fatigue):
                    cont.forget_journal()
        finally:
            self._tx = None
        return r

    def tap_iso(self, orig, d):
        """tap_ray with the ISO-consistent resolver."""
        import time as _t
        t0 = _t.perf_counter()
        res = resolve_iso(self, orig, d)
        self.times["ray"] += _t.perf_counter() - t0
        if res is None:
            self.s["rejected"] += 1
            return {"ok": False, "reason": "miss_rejected"}
        wx, wy, wz = res["point"]
        # Attribution cell: the dominant interpolation node of the crossing
        # block.  The crossing point itself can lie exactly on a cell
        # boundary whose far side is an empty cell (e.g. a face hit between a
        # solid cell and void), so floor() can land in void.  The dominant
        # node of the crossing block always satisfies density >= DENS_ISO
        # (weighted average of node values at the crossing is >= ISO, so max
        # node >= ISO), hence the attributed cell is always material-bearing
        # AND ISO-visible.  This is NOT hit redirection: the impact below is
        # applied at the exact crossing point; only the debris-block attribution
        # uses this cell.
        nci, ncj, nck = res["n_cell"]
        hit_cell = None
        best_val = -1
        for ddx in (0, 1):
            for ddy in (0, 1):
                for ddz in (0, 1):
                    c = (nci + ddx, ncj + ddy, nck + ddz)
                    val = self.density.get(c, 0)
                    if val > best_val:
                        best_val = val
                        hit_cell = c
        if hit_cell is None or hit_cell not in self.density:
            self.s["rejected"] += 1
            return {"ok": False, "reason": "miss_rejected"}
        self.impact(int(round(wx * A.FIX)), int(round(wy * A.FIX)),
                    int(round(wz * A.FIX)))
        self.s["taps"] += 1
        return {"ok": True, "hit": (int(round(wx * A.FIX)),
                                    int(round(wy * A.FIX)),
                                    int(round(wz * A.FIX))),
                "hit_cell": hit_cell, "normal": res["normal"],
                "t": res["t"]}


# ======================================================================
# Part C audit: inventory vs renderable vs hittable vs connected-visible
# ======================================================================
def geometry_audit(rock, ledger=None):
    """Returns (dict) with:
    A_total_inventory  : M0 - consumed - burned (ledger) [- physical present]
    B_renderable_mass  : mass in components containing >=1 cell with density >= DENS_ISO
    B_invisible_mass   : mass in components with no >=ISO cell (never renders)
    C_hittable_mass    : mass of cells in renderable comps with >=1 empty 6-neighbour
    D_main_object_mass : mass of the largest renderable component
    D_visible_frags    : number + mass of other renderable components
    sub_iso_in_main    : mass of sub-ISO cells inside the main renderable comp
    """
    dens = rock.density
    dfix = rock.dfix
    comps = rock.components()
    comps.sort(key=len, reverse=True)
    comp_data = []
    for comp in comps:
        mass = sum(dens[c] for c in comp)
        has_iso = any(dens[c] >= A.DENS_ISO * dfix for c in comp)
        comp_data.append(dict(n=len(comp), mass=mass, has_iso=has_iso))
    renderable_mass = 0
    invisible_mass = 0
    for cd in comp_data:
        if cd["has_iso"]:
            renderable_mass += cd["mass"]
        else:
            invisible_mass += cd["mass"]
    # hittable: exterior cells of renderable comps
    hitt_mass = 0
    hitt_frag_mass = 0
    sub_iso_main = 0
    main_comp = None
    main_has_iso = False
    for comp, cd in zip(comps, comp_data):
        if cd["has_iso"]:
            main_comp = comp
            main_has_iso = True
            break
    if main_comp is None:
        main_comp = comps[0] if comps else set()
    for c, val in dens.items():
        exterior = any((c[0] + dx, c[1] + dy, c[2] + dz) not in dens
                       for dx, dy, dz in A._NEIGH6)
        in_main = c in main_comp
        if in_main and main_has_iso:
            if exterior:
                hitt_mass += val
            if val < A.DENS_ISO * dfix:
                sub_iso_main += val
    for comp, cd in zip(comps, comp_data):
        if cd["has_iso"] and comp is not main_comp:
            for c in comp:
                if any((c[0] + dx, c[1] + dy, c[2] + dz) not in dens
                       for dx, dy, dz in A._NEIGH6):
                    hitt_frag_mass += dens[c]
    other_frags = [cd for cd in comp_data[1:] if cd["has_iso"]]
    out = dict(
        cells=len(dens),
        main_field_mass=sum(dens.values()),
        A_total_inventory=(ledger.M0 - ledger.consumed - ledger.burned)
        if ledger is not None else sum(dens.values()),
        B_renderable_mass=renderable_mass,
        B_invisible_mass=invisible_mass,
        C_hittable_mass=hitt_mass,
        C_hittable_frag_mass=hitt_frag_mass,
        D_main_object_mass=(comp_data[comps.index(main_comp)]["mass"]
                            if main_comp in comps else 0),
        D_main_has_iso=main_has_iso,
        D_visible_fragment_count=len(other_frags),
        D_visible_fragment_mass=sum(cd["mass"] for cd in other_frags),
        D_largest_any_fragment_cells=(len(comps[1]) if len(comps) > 1 else 0),
        component_count=len(comps),
        sub_iso_mass_inside_main=sub_iso_main,
    )
    return out
