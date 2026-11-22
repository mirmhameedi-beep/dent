"""DENT Stage 0.3 — EXP HIST: five impact histories under the Model A calibration.

Histories (all deterministic, same initial rock, gen_rock2(48), L=72):
  A_concentrated : 40 clustered rays round-robin (Stage 0.2 V1 pattern)
  B_distributed  : uniform random surface rays (same stream as s02_completion)
  C_clustered    : 5 distinct ~8-cell patches, round-robin
  D_edge         : impacts concentrated on edge/corner cells detected at init
  E_adaptive     : 60% of taps re-target the region hit most often so far,
                   40% uniform (participants chase softened material)

Calibration (Model A, per-rock derived — see report section 4):
  capacity_per_cell = measured (d0_mean - DENS_FAIL);  C = capacity/1e9
  alpha = C / budget_per_alpha  where budget_per_alpha is the measured
  density-descent per alpha-unit from the s03_attr alpha window (15.33).
  cap_mass=C bounds every accepted tap's total carve; with cell loss via
  carve only (proven by s03_attr), full depletion cannot occur before 1e9
  accepted taps (derived bound; overshoot <= 30 units/cell once each).

Usage: python3 s03_hist.py <HIST> <TARGET_ACCEPTED> [milestones...]
e.g.  python3 s03_hist.py B_distributed 10000000 10000 100000 1000000 10000000

Each checkpoint: appends a metrics row to out/s03_hist/<HIST>/metrics.jsonl
and pickles the full resumable state to state_<accepted>.pkl / state_last.pkl.
"""
import json, math, os, pickle, random, sys, time

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s03_rock as R3

OUTDIR = "out/s03_hist"
BUDGET_PER_ALPHA = 15.33   # measured (s03_attr ALPHA window: 0.035146/0.002292)


def ray_into(rock, tgt, vd):
    ln = math.sqrt(sum(c * c for c in vd)); u = tuple(c / ln for c in vd)
    return (tuple(int((tgt[i] + u[i] * 4.0) * FIX) for i in range(3)),
            tuple(int(-c * FIX) for c in u))


def make_rock(hist, lattice=72):
    verts, tris = gen_rock2(48)
    rock = R3.RockDensity(verts, tris, lattice=lattice, alpha=1.0, dfix=65536)
    # Model A per-rock calibration (derived constants, measured inputs)
    dsum = sum(rock.density.values()) / rock.dfix
    cells0 = len(rock.density)
    d0mean = dsum / cells0
    cap = (d0mean - 30.0) * cells0 / 1e9
    rock.alpha = cap / BUDGET_PER_ALPHA
    rock.cap_mass = cap
    rock.calib = dict(cells0=cells0, dens_sum0=dsum, d0mean=round(d0mean, 3),
                      cap_mass=cap, alpha=round(rock.alpha, 8))
    return rock


def edge_cells(rock):
    """Cells at sharp edges/corners: boundary cells with <=3 live 6-neighbours."""
    out = []
    for c in rock.density:
        n = sum(1 for dx, dy, dz in R3._NEIGH6
                if (c[0]+dx, c[1]+dy, c[2]+dz) in rock.density)
        if n <= 3:
            out.append(c)
    return out


def cluster_targets(rock, k=5, seed=77):
    """k distinct surface patches far apart."""
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
    """Deterministic tap source per history."""
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

    def source(self):
        h = self.hist
        r = self.rnd
        if h == "A_concentrated":
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
            tgt = tuple(self.rock.origin + (c[i2] + 0.5) * self.rock.cs + r.uniform(-0.01, 0.01) for i2 in range(3))
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
        if self.hist == "E_adaptive":
            self.counts[hit_pt] = self.counts.get(hit_pt, 0) + 1
            if hit_pt not in self.order:
                self.order.append(hit_pt)
            if len(self.order) > 400:
                # stable sort: -count primary, insertion order preserved for ties
                self.order.sort(key=lambda p: -self.counts[p])
                self.order = self.order[:40]
                self.counts = {p: self.counts[p] for p in self.order}


def _rss():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    except Exception:
        return -1


def metrics_row(rock, hist_stream, accepted, launched, t_elapsed):
    dfix = rock.dfix
    dens = rock.density
    n = len(dens)
    faces = 0
    bands = [0] * 4
    for c, d in dens.items():
        dl = d / dfix
        bands[max(0, min(3, int((dl - 30) // 45)))] += 1
        for dx, dy, dz in R3._NEIGH6:
            if (c[0]+dx, c[1]+dy, c[2]+dz) not in dens:
                faces += 1
    try:
        comps = rock.components()
        frag_count = max(0, len(comps) - 1)
        largest = max((len(x) for x in comps), default=0)
    except Exception:
        frag_count = largest = None
    fatigue400 = sum(1 for v in rock.fatigue.values() if v > 400)
    row = dict(hist=hist_stream.hist, accepted=accepted, launched=launched,
               elapsed_s=round(t_elapsed, 1),
               cells=n, cells0=rock.calib["cells0"],
               dens_sum=round(sum(dens.values()) / dfix, 1),
               dens_sum0=rock.calib["dens_sum0"],
               mass_removed_cells=rock.s["crumbles"],
               sev_total=rock.s["sev_total"],
               surface_area_faces=faces,
               surface_area_est=round(faces * rock.cs * rock.cs, 5),
               bands_30_60=bands[0], bands_60_120=bands[1],
               bands_120_180=bands[2], bands_180_240=bands[3],
               rejected=rock.s["rejected"],
               hash=rock.hash_state(),
               rss_mb=round(_rss(), 1))
    if frag_count is not None:
        row["fragments"] = frag_count
        row["largest_frag"] = largest
    row["fatigue400"] = fatigue400
    return row


def run(hist, target, milestones, lattice=72, seed=4242):
    d = os.path.join(OUTDIR, hist)
    os.makedirs(d, exist_ok=True)
    mpath = os.path.join(d, "metrics.jsonl")
    pkl = os.path.join(d, "state_last.pkl")
    rows = [json.loads(l) for l in open(mpath) if l.strip()] if os.path.exists(mpath) else []
    if rows and os.path.exists(pkl):
        with open(pkl, "rb") as f:
            rock, hist_stream = pickle.load(f)
        rock._mat_cache = {}
        # attribute-default shim: checkpoints saved by the pre-12:21 engine
        # lack the new stage-0.3 config attrs; set them to the exact defaults
        # the running 30M processes used (Model A: beta off, support off,
        # grain off) so CURRENT s03_rock.py methods cannot AttributeError.
        for a, v in (("beta", 0.0), ("support", False), ("grain", False)):
            if not hasattr(rock, a):
                setattr(rock, a, v)
        acc = rows[-1]["accepted"]
        print(f"[{hist}] resuming at accepted={acc}, target={target}", flush=True)
    else:
        rock = make_rock(hist, lattice)
        hist_stream = HistStream(rock, hist, seed)
        json.dump(rock.calib, open(os.path.join(d, "calib.json"), "w"))
        acc = 0
        rock._mat_cache = {}
        with open(pkl, "wb") as f:
            pickle.dump((rock, hist_stream), f, 2)
        print(f"[{hist}] fresh start; calib={rock.calib}", flush=True)
    mile = sorted([m for m in milestones if m > acc])
    t0 = time.time()
    launched = 0
    while acc < target and rock.density:
        launched += 1
        tgt, vd = hist_stream.source()
        o, dvec = ray_into(rock, tgt, vd)
        r = rock.tap_ray(o, dvec)
        if r["ok"]:
            acc += 1
            hist_stream.record(r["hit"])
        if mile and acc >= mile[0]:
            m = mile.pop(0)
            row = metrics_row(rock, hist_stream, acc, launched, time.time() - t0)
            with open(mpath, "a") as f:
                f.write(json.dumps(row) + "\n")
            rock._mat_cache = {}
            with open(os.path.join(d, f"state_{acc}.pkl"), "wb") as f:
                pickle.dump((rock, hist_stream), f, 2)
            with open(pkl, "wb") as f:
                pickle.dump((rock, hist_stream), f, 2)
            print(f"[{hist}] milestone {m}: acc={acc} cells={row['cells']} "
                  f"removed={row['mass_removed_cells']} sev={row['sev_total']} "
                  f"frag={row.get('fragments')} rej={row['rejected']} "
                  f"rss={row['rss_mb']}MB t={row['elapsed_s']}s", flush=True)
    print(f"[{hist}] done acc={acc} launched={launched} cells={len(rock.density)} "
          f"sec={time.time()-t0:.0f}", flush=True)
    row = metrics_row(rock, hist_stream, acc, launched, time.time() - t0)
    with open(mpath, "a") as f:
        f.write(json.dumps(row) + "\n")
    with open(os.path.join(d, "state_final.pkl"), "wb") as f:
        pickle.dump((rock, hist_stream), f, 2)


if __name__ == "__main__":
    hist = sys.argv[1]
    target = int(sys.argv[2])
    miles = [int(x) for x in sys.argv[3:]] or [10_000, 100_000, 1_000_000, 10_000_000]
    run(hist, target, miles)
