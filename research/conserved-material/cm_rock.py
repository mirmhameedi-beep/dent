"""Conserved-material rock engine (POC, scratch).

Subclasses modelA_stage03.RockDensity (byte-identical copy of the Stage 0.3
Model A engine) and reroutes every material delta into an integer conserved
ledger. Rays, carve kernel, bond lattice and severing are UNCHANGED; only the
fate of removed material differs, plus the derived consumption allowance and
the terminal event.

Ledger identities (integers, dfix units = legacy density unit / 65536):

    M0 == density_sum(field: main+fragments) + debris + fines + consumed + burned

Routes:
  * clipped carve take  -> consumed (bounded by per-tap allowance q) + debris[block]
  * crumble residual    -> debris[block] (transfer; never silent deletion)
    (bounded once per cell by DENS_FAIL dfix units -> structured crumble slack)
  * integer round-off    -> included in the integer delta actually applied
  * debris 'shed' policy -> fines (finer tier), impacted blocks only
  * terminal event       -> field + debris + fines -> burned (idempotent)

q = (M0 - Mr) // N  (exact integer floor; Mr >= DENS_FAIL * cells0 so the
one-off crumble slack can never push the inventory below reserve).

The per-tap two-pass clip uses cap = q (legacy units), i.e. the SAME erosion
bound as Model A with C = capacity_per_cell; the conserved ledger is the
addition. Main-rock erosion is therefore directly comparable to Model A.

Pure stdlib. Scratch experiment only - NOT product code.
"""
import modelA_stage03 as A
from modelA_stage03 import DENS_FAIL, vkey

BLOCK = 6            # debris macro-block side (cells); L=72 -> 12^3 blocks
HB = 6               # hierarchical DDA block side (cells)


class ConservedRock(A.RockDensity):

    def __init__(self, verts, tris, lattice=72, N=20_000,
                 reserve_frac=0.02, mode="per_tap", debris_policy="hold",
                 dfix=65536, kappa=0.5):
        super().__init__(verts, tris, lattice=lattice, dfix=dfix)
        self.M0 = sum(self.density.values())
        self.cells0 = len(self.density)
        crumble_slack = DENS_FAIL * self.cells0 * dfix
        self.Mr = max(crumble_slack + 1, int(self.M0 * reserve_frac))
        self.N = N
        self.q_tap = (self.M0 - self.Mr) // N          # dfix units, floor
        self.q_legacy = self.q_tap / dfix
        self.mode = mode
        self.kappa = kappa        # fraction of clipped carve take -> consumed
        self.debris_policy = debris_policy
        self.debris = {}        # block -> int mass (dfix)
        self.fines = {}         # block -> int mass (finer tier)
        self.debris_hits = {}   # block -> impacts received (shed policy)
        self.debris_shed = {}   # block -> shed events
        self.consumed = 0       # irreversible (dfix)
        self.burned = 0         # terminal-event transfer (dfix)
        self.main_mass = self.M0
        self.terminal_done = False
        self.manifest = None
        self.blocks_touched_last = 0
        self.modified_last = 0
        # force the capped two-pass carve path; _apply_carves is overridden
        self.cap_mass = self.q_legacy
        # hierarchical ray support
        self.block_count = {}
        for (i, j, k) in self.density.keys():
            b = (i // HB, j // HB, k // HB)
            self.block_count[b] = self.block_count.get(b, 0) + 1
        self.calib = dict(cells0=self.cells0, dens_sum0=self.M0 / dfix,
                          Mr=self.Mr, Mr_frac=self.Mr / self.M0,
                          q_tap_dfix=self.q_tap, q_legacy=self.q_legacy,
                          mode=mode, reserve_frac=reserve_frac,
                          debris_policy=debris_policy, N=N, kappa=kappa)

    # ---------- ledger routing ----------
    def _debris_add(self, cell, mass):
        if mass <= 0:
            return
        b = (cell[0] // BLOCK, cell[1] // BLOCK, cell[2] // BLOCK)
        self.debris[b] = self.debris.get(b, 0) + mass

    def _consume_or_debris(self, cell, residual, budget, frac=0.5):
        """Split an integer residual of removed material: frac -> irreversibly
        consumed (never exceeding the budget), remainder -> debris transfer."""
        use = int(residual * frac)
        if use > budget:
            use = budget
        if use < 0:
            use = 0
        self.consumed += use
        if residual - use:
            self._debris_add(cell, residual - use)
        return budget - use

    def _apply_carves(self, takes, wx, wy, wz, cs, org, ci, cj, ck, R, rc,
                      removed_now):
        budget = self.q_tap if self.mode == "per_tap" \
            else (self.M0 - self.Mr - self.consumed)
        total = sum(t for _, t, _ in takes)
        f = min(1.0, self.cap_mass / total) if (self.cap_mass and total > 0) else 1.0
        fa = self.attr
        touched = set()
        mod = 0
        for cell, take, dcur in takes:
            tf = take * f * self.dfix
            newd = dcur - tf
            if newd < DENS_FAIL * self.dfix:
                residual = dcur                       # whole cell leaves the field
                budget = self._consume_or_debris(cell, residual, budget,
                                                 frac=self.kappa)
                self.density.pop(cell, None)
                self.fatigue.pop(vkey(*cell, self.L), None)
                removed_now.append(cell)
                self.s["crumbles"] += 1
                d0l = dcur / self.dfix
                fa["removals"] += 1
                fa["take_sum"] += take * f
                if take * f >= d0l - DENS_FAIL:
                    fa["single_tap_kills"] += 1
                fa["pre_death_bucket"][min(7, int(d0l / 30))] += 1
                if fa["first_removal_tap"] is None:
                    fa["first_removal_tap"] = self.s["taps"] + 1
                self.main_mass -= dcur
                mod += 1
                touched.add((cell[0] // BLOCK, cell[1] // BLOCK, cell[2] // BLOCK))
            else:
                newd_int = int(round(newd))
                residual = dcur - newd_int            # exact applied integer delta
                budget = self._consume_or_debris(cell, residual, budget,
                                                 frac=self.kappa)
                self.density[cell] = newd_int
                if fa["first_sub120_tap"] is None and newd_int / self.dfix < 120:
                    fa["first_sub120_tap"] = self.s["taps"] + 1
                if fa["first_sub200_tap"] is None and newd_int / self.dfix < 200:
                    fa["first_sub200_tap"] = self.s["taps"] + 1
                self.main_mass -= residual
                if residual > 0:
                    mod += 1
                touched.add((cell[0] // BLOCK, cell[1] // BLOCK, cell[2] // BLOCK))
        self.modified_last = mod
        for cell in removed_now:
            if cell in self.density:
                self.density.pop(cell)
            b = (cell[0] // HB, cell[1] // HB, cell[2] // HB)
            c = self.block_count.get(b, 0)
            if c:
                self.block_count[b] = c - 1
        self.blocks_touched_last = len(touched)

    # ---------- debris policies ----------
    def debris_after_tap(self, hit_cell):
        if self.debris_policy != "shed":
            return
        b = (hit_cell[0] // BLOCK, hit_cell[1] // BLOCK, hit_cell[2] // BLOCK)
        m = self.debris.get(b, 0)
        if not m:
            return
        h = self.debris_hits.get(b, 0) + 1
        self.debris_hits[b] = h
        if h % 3:
            return
        budget = self.q_tap - 0
        moved = m // 4
        if not moved:
            return
        use = moved // 2
        if use > budget:
            use = budget
        self.debris[b] = m - moved
        self.fines[b] = self.fines.get(b, 0) + moved - use
        self.debris_shed[b] = self.debris_shed.get(b, 0) + 1
        self.consumed += use

    # ---------- tap ----------
    def tap_ledger(self, orig, d):
        n0 = self.s["taps"]
        r = self.tap_ray(orig, d)
        if r.get("ok"):
            self.debris_after_tap(r["hit_cell"])
            n = self.s["taps"]
            self._check_invariant(n)
        return r

    def _check_invariant(self, n):
        debris_total = sum(self.debris.values()) + sum(self.fines.values())
        physical = self.main_mass + debris_total
        if physical != self.M0 - self.consumed - self.burned:
            self.violations_ledger = getattr(self, "violations_ledger", [])
            self.violations_ledger.append(
                dict(tap=n, main=self.main_mass, debris=debris_total,
                     consumed=self.consumed, burned=self.burned, M0=self.M0))
        if self.consumed > n * self.q_tap + self.burned:
            self.violations_allowance = getattr(self, "violations_allowance", [])
            self.violations_allowance.append(
                dict(tap=n, consumed=self.consumed, n=n, q=self.q_tap))
        if n < self.N and physical <= self.Mr:
            self.violations_reserve = getattr(self, "violations_reserve", [])
            self.violations_reserve.append(
                dict(tap=n, physical=physical, Mr=self.Mr))
        return physical

    def audit_ledger(self):
        """O(V) full recount; returns (ok, detail)."""
        ds = sum(self.density.values())
        debris_total = sum(self.debris.values()) + sum(self.fines.values())
        ident = ds + debris_total + self.consumed + self.burned - self.M0
        drift = ds - self.main_mass
        comps = self.components()
        comps.sort(key=len, reverse=True)
        return dict(balance_residual=ident, tracker_drift=drift,
                    fines_total=sum(self.fines.values()),
                    density_sum=ds, main_mass=self.main_mass,
                    debris_total=debris_total, consumed=self.consumed,
                    burned=self.burned, M0=self.M0,
                    fragment_components=max(0, len(comps) - 1),
                    fragment_cells=sum(len(c) for c in comps[1:]) if len(comps) > 1 else 0,
                    largest_fragment=len(comps[0]) if comps else 0)

    # ---------- hierarchical ray (Option C element) ----------
    def resolve_ray_fast(self, orig, d):
        L, cs, org = self.L, self.cs, self.origin
        ox, oy, oz = orig
        dx_, dy_, dz_ = d
        ln = A.math.sqrt(dx_ * dx_ + dy_ * dy_ + dz_ * dz_) or 1
        dx_, dy_, dz_ = dx_ / ln, dy_ / ln, dz_ / ln
        wi, wj, wk = ox / A.FIX, oy / A.FIX, oz / A.FIX
        i = int(A.math.floor((wi - org) / cs))
        j = int(A.math.floor((wj - org) / cs))
        k = int(A.math.floor((wk - org) / cs))
        step = [0, 0, 0]
        tmax = [0.0, 0.0, 0.0]
        td = [0.0, 0.0, 0.0]
        pos = [wi, wj, wk]
        dv = [dx_, dy_, dz_]
        for axis in range(3):
            if dv[axis] == 0:
                tmax[axis] = 1e30
                td[axis] = 1e30
            else:
                ci = int(A.math.floor((pos[axis] - org) / cs))
                nb = org + (ci + 1) * cs if dv[axis] > 0 else org + ci * cs
                tmax[axis] = (nb - pos[axis]) / dv[axis]
                td[axis] = abs(cs / dv[axis])
                step[axis] = 1 if dv[axis] > 0 else -1
        t_enter = 0.0
        contact = None
        for _ in range(3 * L + 8):
            if 0 <= i < L and 0 <= j < L and 0 <= k < L \
                    and (i, j, k) in self.density:
                contact = (i, j, k)
                break
            m = tmax[0]
            ax = 0
            if tmax[1] < m:
                m = tmax[1]
                ax = 1
            if tmax[2] < m:
                m = tmax[2]
                ax = 2
            if m > self.span * 2.2:
                break
            b = (i // HB, j // HB, k // HB)
            if 0 <= i < L and 0 <= j < L and 0 <= k < L \
                    and self.block_count.get(b, 0) == 0 and step[ax] != 0:
                # jump along ax only if the block-exit along ax precedes any
                # other axis' next boundary crossing (else a diagonal ray must
                # leave the block the normal way first)
                cur = (i, j, k)[ax]
                bit = (i // HB, j // HB, k // HB)[ax]
                if step[ax] > 0:
                    land = bit * HB + HB
                    t_land = m + (land - cur - 1) * td[ax]
                else:
                    land = bit * HB - 1
                    t_land = m + (cur - land - 1) * td[ax]
                others = [tmax[a2] for a2 in range(3)
                          if a2 != ax and tmax[a2] < 1e29]
                if others and t_land >= min(others):
                    pass
                elif t_land > self.span * 2.2:
                    break
                else:
                    t_enter = t_land
                    tmax[ax] = t_land + td[ax]
                    if ax == 0:
                        i = land
                    elif ax == 1:
                        j = land
                    else:
                        k = land
                    continue
            if ax == 0:
                i += step[0]
            elif ax == 1:
                j += step[1]
            else:
                k += step[2]
            tmax[ax] += td[ax] if td[ax] < 1e29 else 1.0
            t_enter = m
        if contact is None:
            return None
        cx, cy, cz = org + (contact[0] + 0.5) * cs, \
            org + (contact[1] + 0.5) * cs, org + (contact[2] + 0.5) * cs

        def dens_t(t):
            return self.trilerp_density(wi + t * dx_, wj + t * dy_, wk + t * dz_)

        lo = t_enter - 0.85 * cs
        hi = A.math.sqrt((cx - wi) ** 2 + (cy - wj) ** 2 + (cz - wk) ** 2)
        for _ in range(3):
            if dens_t(lo) >= A.DENS_ISO:
                lo -= cs
            else:
                break
        if dens_t(lo) >= A.DENS_ISO:
            return (round(cx * A.FIX), round(cy * A.FIX), round(cz * A.FIX)), contact
        for _ in range(14):
            mid = (lo + hi) / 2
            if dens_t(mid) >= A.DENS_ISO:
                hi = mid
            else:
                lo = mid
        t = hi
        wx, wy, wz = wi + t * dx_, wj + t * dy_, wk + t * dz_
        return (round(wx * A.FIX), round(wy * A.FIX), round(wz * A.FIX)), contact

    # ---------- terminal ----------
    def terminal_event(self, accepted_n=None, expected_N=None):
        """Authorised only at exactly N accepted. Idempotent."""
        if self.terminal_done:
            return dict(idempotent_replay=True, manifest=self.manifest)
        if expected_N is not None and expected_N != self.N:
            return dict(authorised=False, reason="counter_mismatch")
        if accepted_n is not None and accepted_n != self.N:
            return dict(authorised=False, reason="accepted_counter_mismatch")
        pre = self.audit_ledger()
        pre_hash = self.hash_state()
        self.burned += sum(self.density.values()) \
            + sum(self.debris.values()) + sum(self.fines.values())
        self.density = {}
        self.severed = set()
        self.bdamage = {}
        self.fatigue = {}
        self.debris = {}
        self.fines = {}
        self.block_count = {}
        self.terminal_done = True
        self.manifest = dict(event="terminal_disintegration",
                             accepted=accepted_n if accepted_n is not None else self.N,
                             N_target=self.N,
                             pre_hash=pre_hash,
                             physical_before=pre["density_sum"] + pre["debris_total"],
                             burned=self.burned,
                             reserve=self.Mr,
                             version="cm_poc_v1")
        post = self.audit_ledger()
        ok = post["balance_residual"] == 0 and post["density_sum"] == 0 \
            and post["debris_total"] == 0 and self.burned == self.M0 - self.consumed
        self.manifest["post_audit_ok"] = bool(ok)
        self.manifest["post_hash"] = self.hash_state()
        return self.manifest
