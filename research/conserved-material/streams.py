"""Deterministic tap streams shared by the POC experiments.

Mirrors the Stage 0.3 history streams (A_concentrated, B_distributed,
C_clustered, D_edge, E_adaptive) so results are comparable, plus a HOSTILE
stream (deterministic bore-until-miss with pivot list).
"""
import math
import random

import modelA_stage03 as A
from common import FIX


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd))
    u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def edge_cells(rock):
    out = []
    for c in list(rock.density.keys())[:60000]:
        n = sum(1 for dx, dy, dz in A._NEIGH6
                if (c[0] + dx, c[1] + dy, c[2] + dz) in rock.density)
        if n <= 3:
            out.append(c)
    return out


def cluster_targets(rock, k=5, seed=77):
    rnd = random.Random(seed)
    cells = list(rock.density.keys())

    def centre(c):
        return tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))

    picks = []
    for _ in range(40000):
        c = rnd.choice(cells)
        p = centre(c)
        if picks and min(math.dist(p, centre(q)) for q in picks) > 0.8:
            picks.append(c)
            if len(picks) == k:
                break
        if not picks:
            picks.append(c)
    while len(picks) < k:
        picks.append(rnd.choice(cells))
    return [centre(c) for c in picks]


class HistStream:
    """Same patterns as s03_hist.HistStream (Stage 0.3)."""

    def __init__(self, rock, hist, seed=4242):
        self.rock = rock
        self.hist = hist
        self.rnd = random.Random(seed)
        if hist == "A_concentrated":
            self.rays = []
            for q in range(40):
                vd = (0.35 + 0.01 * (q % 5) - 0.02, -0.25 + 0.01 * (q // 5) - 0.02, 0.91)
                self.rays.append(((0.35, 0.30, 0.0), vd))
            self.i = 0
        elif hist == "C_clustered":
            self.patches = cluster_targets(rock)
            self.i = 0
        elif hist == "D_edge":
            self.edges = edge_cells(rock)
            self.rnd.shuffle(self.edges)
            self.i = 0
        elif hist == "E_adaptive":
            self.counts = {}
            self.order = []
        elif hist == "A_rot":
            self.rays = []
            for q in range(40):
                vd = (0.35 + 0.01 * (q % 5) - 0.02, -0.25 + 0.01 * (q // 5) - 0.02, 0.91)
                self.rays.append(((0.35, 0.30, 0.0), vd))
            self.i = 0
            self.accepts = 0
            self.rot = 0

    def source(self):
        h, r = self.hist, self.rnd
        if h == "A_concentrated":
            tgt, vd = self.rays[self.i % len(self.rays)]
            self.i += 1
            return tgt, vd
        if h == "A_rot":
            tgt, vd = self.rays[self.i % len(self.rays)]
            self.i += 1
            return tgt, vd
        if h == "B_distributed":
            return ((r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6)),
                    (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(0.5, 1.1)))
        if h == "C_clustered":
            tgt = self.patches[self.i % len(self.patches)]
            self.i += 1
            jitter = (r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03), r.uniform(-0.03, 0.03))
            return (tuple(tgt[i2] + jitter[i2] for i2 in range(3)),
                    (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(0.5, 1.1)))
        if h == "D_edge":
            c = self.edges[self.i % max(1, len(self.edges))]
            self.i += 1
            tgt = tuple(self.rock.origin + (c[i2] + 0.5) * self.rock.cs
                        + r.uniform(-0.01, 0.01) for i2 in range(3))
            return tgt, (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(0.5, 1.1))
        if h == "E_adaptive":
            if self.counts and r.random() < 0.60:
                best = max(self.order, key=lambda p: self.counts[p])
                tgt = tuple(best[i2] + r.uniform(-0.04, 0.04) for i2 in range(3))
            else:
                tgt = (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6))
            return tgt, (r.uniform(-0.6, 0.6), r.uniform(-0.6, 0.6), r.uniform(0.5, 1.1))
        raise ValueError(h)

    def record(self, hit_pt):
        if self.hist == "A_rot":
            self.accepts += 1
            if self.accepts % 20 == 0:
                self.rot += 1
                r2 = random.Random(9000 + self.rot)
                self.rays = []
                for q in range(40):
                    vd = (r2.uniform(-0.6, 0.6), r2.uniform(-0.6, 0.6),
                          r2.uniform(0.5, 1.1))
                    tgt = (r2.uniform(-0.6, 0.6), r2.uniform(-0.6, 0.6),
                           r2.uniform(-0.6, 0.6))
                    self.rays.append((tgt, vd))
                self.i = 0
        if self.hist == "E_adaptive":
            self.counts[hit_pt] = self.counts.get(hit_pt, 0) + 1
            if hit_pt not in self.order:
                self.order.append(hit_pt)
            if len(self.order) > 400:
                self.order.sort(key=lambda p: -self.counts[p])
                self.order = self.order[:40]
                self.counts = {p: self.counts[p] for p in self.order}


class HostileStream:
    """Sequentially focused worst-case stream: hammers ONE deterministic
    target until the recent acceptance rate collapses (bore exhausted), then
    pivots to a fresh deterministic surface target. Maximally hostile spatial
    history for the ledger (minimal set of regions, deep bores), but remains
    able to reach N accepted taps by construction."""

    def __init__(self, rock, seed=4242, window=500, min_rate=0.5):
        self.rock = rock
        self.rnd = random.Random(seed)
        self.window = window
        self.min_rate = min_rate
        self.launched_in_window = 0
        self.accepted_in_window = 0
        self.pivots = 0
        self.tgt = self._pick()

    def _pick(self):
        t = (self.rnd.uniform(-0.6, 0.6), self.rnd.uniform(-0.6, 0.6),
             self.rnd.uniform(-0.6, 0.6))
        self.pivots += 1
        return t

    def source(self):
        if self.launched_in_window >= self.window and \
                self.accepted_in_window < self.min_rate * self.window:
            self.tgt = self._pick()
            self.launched_in_window = 0
            self.accepted_in_window = 0
        vd = (self.rnd.uniform(-0.6, 0.6), self.rnd.uniform(-0.6, 0.6),
              self.rnd.uniform(0.5, 1.1))
        self.launched_in_window += 1
        return self.tgt, vd

    def record(self, hit_pt):
        self.accepted_in_window += 1


def run_stream(rock, stream, target_accepted, milestones=()):
    """Tap until target_accepted ACCEPTED taps (misses rejected, as in the
    Stage 0.3 history runs). Returns dict of ledger snapshots at milestones."""
    accepted = 0
    launched = 0
    snaps = {}
    ml = sorted(milestones)
    ms = set(ml)
    max_launched = 40 * target_accepted
    t0 = __import__("time").perf_counter()
    while accepted < target_accepted and launched < max_launched:
        tgt, vd = stream.source()
        orig, d = ray_into(rock, tgt, vd)
        r = rock.tap_ledger(orig, d)
        launched += 1
        if r.get("ok"):
            accepted = rock.s["taps"]
            stream.record(r["hit"])
        if accepted in ms and accepted not in snaps:
            snaps[accepted] = rock.audit_ledger()
    snaps["wall_s"] = round(__import__("time").perf_counter() - t0, 1)
    snaps["accepted"] = accepted
    snaps["launched"] = launched
    return snaps
