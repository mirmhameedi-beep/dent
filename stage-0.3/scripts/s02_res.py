"""DENT Stage 0.2 — Experiment RES: resolution & storage benchmark.

For L in (72, 96, 128, 176-if-fits) on the SAME test rock:
  memory (VmRSS) at init / after localized crater / after distributed damage
  per-impact time (normal + pathological incl. reject fast-path)
  raycast time, connectivity time, hash time
  blocky + MT extraction time & triangle counts (MT only L<=96)
  snapshot size (packed uint32 keys + uint8 densities + uint64 severed)
  recovery: fresh voxelize + snapshot apply -> exact state-hash match
All times are scratch-machine (5 vCPU, 6 GB, shared with concurrent lifecycle
run for the early rows) — NOT Railway figures.
Output: out/s02_res_results.json
"""
import json, os, random, struct, sys, time, tracemalloc

sys.path.insert(0, '.')
from common import gen_rock2, FIX
import s02_rock as R2
import s02_mt as MT

OUT = "out"
FIXTURE_SAME_ROCK = ()


def rss_mb():
    with open('/proc/self/status') as f:
        for line in f:
            if line.startswith('VmRSS'):
                return round(int(line.split()[1]) / 1024.0, 1)
    return -1


def pack_snapshot(rock):
    """Compact authority snapshot: sorted (vkey, density) + severed bond keys."""
    L = rock.L
    items = sorted(rock.density.items())
    keys = [R2.vkey(c[0], c[1], c[2], L) for c, _ in items]
    dens = [d for _, d in items]
    severed = sorted(rock.severed)
    blob = struct.pack('<I', L) + struct.pack('<I', len(keys)) \
        + struct.pack('<I', len(severed)) \
        + struct.pack('<%sI' % len(keys), *keys) \
        + struct.pack('<%sB' % len(dens), *dens) \
        + struct.pack('<%sQ' % len(severed), *severed)
    return blob


def apply_snapshot(rock, blob):
    L, n, ns = struct.unpack_from('<III', blob, 0)
    off = 12
    keys = struct.unpack_from('<%sI' % n, blob, off); off += 4 * n
    dens = struct.unpack_from('<%sB' % n, blob, off); off += n
    severed = struct.unpack_from('<%sQ' % ns, blob, off)
    from s02_rock import vunkey
    rock.density = {vunkey(v, L): d for v, d in zip(keys, dens)}
    rock.severed = set(severed)
    return rock


def unit(v):
    ln = (v[0]*v[0]+v[1]*v[1]+v[2]*v[2]) ** 0.5 or 1.0
    return (v[0]/ln, v[1]/ln, v[2]/ln)


def ray_into(rock, tgt, vd):
    vd = unit(vd)
    org = tuple(int((tgt[i] + vd[i]*4.0) * FIX) for i in range(3))
    return org, tuple(int(-c*FIX) for c in vd)


def bench(L, mt_allowed=True, time_budget_s=240):
    row = {"L": L}
    t0 = time.time(); tracemalloc.start()
    verts, tris = gen_rock2(48)
    rock = R2.RockDensity(verts, tris, lattice=L)
    tracemalloc.stop()
    row["init_s"] = round(time.time()-t0, 2)
    row["rss_mb_init"] = rss_mb()
    row["cells"] = len(rock.density)
    row["cs_world"] = round(rock.cs, 6)
    n_est = row["cells"] * 5
    row["snapshot_bytes_pristine"] = len(pack_snapshot(rock))

    def timed_taps(label, rays, taps_each):
        t = time.time(); ok = rej = 0; dt0 = time.perf_counter()
        for (o, d) in rays:
            for _ in range(taps_each):
                r = rock.tap_ray(o, d)
                if r["ok"]: ok += 1
                else: rej += 1
        per = (time.perf_counter()-dt0) / max(1, ok+rej) * 1000.0
        row[label] = dict(accepted=ok, rejected=rej, ms_per_tap=round(per, 3))
        return ok

    # NORMAL load: 3000 distributed taps (deterministic)
    rnd = random.Random(4242)
    rays = []
    while len(rays) < 300:
        tgt = (rnd.uniform(-0.55, 0.55), rnd.uniform(-0.55, 0.55), rnd.uniform(-0.55, 0.55))
        rays.append(ray_into(rock, tgt, (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), rnd.uniform(0.5, 1.1))))
    timed_taps("distributed_3000", rays, 10)
    row["rss_mb_after_distributed"] = rss_mb()
    row["snapshot_bytes_distributed3k"] = len(pack_snapshot(rock))

    # PATHOLOGICAL: 3000 at one anchor (bore-through), then 2000 rejected
    tgt = (0.35, 0.30, 0.0)
    o, d = ray_into(rock, tgt, (0.35, -0.25, 0.91))
    timed_taps("pathological_5000", [(o, d)], 5000)
    row["rss_mb_after_pathological"] = rss_mb()
    row["cells_after"] = len(rock.density)
    row["snapshot_bytes_pathological"] = len(pack_snapshot(rock))

    # raycast-only timing (200 resolutions, some may reject post-bore)
    t = time.perf_counter()
    for _ in range(200):
        rock.resolve_ray(o, d)
    row["raycast_ms"] = round((time.perf_counter()-t)/200*1000, 3)

    # connectivity + hash
    t = time.time(); rock.components()
    row["components_s"] = round(time.time()-t, 2)
    t = time.time(); rock.hash_state()
    row["hash_state_s"] = round(time.time()-t, 2)
    t = time.time(); h1 = rock.hash_state()
    row["hash"] = h1

    # extraction: blocky always; MT for small L (time guard)
    t = time.time(); bv, bt = MT.extract_blocky(rock)
    row["blocky"] = dict(s=round(time.time()-t, 2), tris=len(bt),
                         verts=len(bv))
    if mt_allowed:
        t = time.time(); mv, mn, mt = MT.extract_mt(rock)
        row["mt"] = dict(s=round(time.time()-t, 2), tris=len(mt), verts=len(mv))

    # recovery: fresh voxelize + apply snapshot -> exact hash match
    t0 = time.time()
    rock2 = R2.RockDensity(verts, tris, lattice=L)
    pv, pd, ps = struct.unpack_from('<III', pack_snapshot(rock), 0)  # sanity
    blob = pack_snapshot(rock)
    apply_snapshot(rock2, blob)
    row["recovery_s_voxelize_plus_apply"] = round(time.time()-t0, 2)
    row["recovery_exact_match"] = rock2.hash_state() == h1
    row["rss_mb_after_recovery"] = rss_mb()
    row["row_total_s"] = round(time.time()-t0, 1)
    return row


def main():
    out = []
    for L, mt_ok in ((72, True), (96, True), (128, False), (176, False)):
        if L == 176 and rss_mb() > 2600:
            out.append({"L": 176, "skipped": "memory budget"}); continue
        try:
            out.append(bench(L, mt_allowed=mt_ok))
        except MemoryError:
            out.append({"L": L, "skipped": "MemoryError"})
        except Exception as e:
            out.append({"L": L, "error": repr(e)})
        json.dump(out, open(f"{OUT}/s02_res_results.json", "w"), indent=1)
        print(json.dumps(out[-1], default=str)[:220], flush=True)
    print("res done")


if __name__ == "__main__":
    main()
