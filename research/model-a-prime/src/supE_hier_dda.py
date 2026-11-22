"""PART E supplement: hierarchical-DDA benchmark on the AUTHENTIC rock.
Mirrors exp6's benchmark (plain DDA vs 2-level block-skipping DDA) but on a
compressed-lifetime damaged authentic state via recalc_conserved()."""
import json
import random
import time

import cm_rock
import modelA_stage03 as A
import maprim_rock as M
import streams
from streams import ray_into
import expB_budget_audit as EB


def main():
    out = {"note": "exp6-style hierarchical DDA on authentic rock, "
                   "A_rot 4000-tap compressed damaged state"}
    verts_tris = None
    from common import gen_rock2
    verts, tris = gen_rock2(48)
    rock = cm_rock.ConservedRock(verts, tris, lattice=72, N=20000,
                                 debris_policy="hold")
    global _p
    EB.PRISTINE = M.load_pristine()
    EB.recalc_conserved(rock)
    rock.alpha = rock.q_legacy / 15.33
    streams.run_stream(rock, streams.HistStream(rock, "A_rot"), 4000)
    empty_blocks = sum(1 for v in rock.block_count.values() if v == 0)
    rnd = random.Random(31337)
    mismatches = 0
    n_bench = 600
    t_plain = t_fast = 0.0
    for _ in range(n_bench):
        tgt = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
               rnd.uniform(-0.6, 0.6))
        vd = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6),
              rnd.uniform(0.5, 1.1))
        orig, d = ray_into(rock, tgt, vd)
        t1 = time.perf_counter()
        r1 = rock.resolve_ray(orig, d)
        t_plain += time.perf_counter() - t1
        t2 = time.perf_counter()
        r2 = rock.resolve_ray_fast(orig, d)
        t_fast += time.perf_counter() - t2
        c1 = r1[1] if r1 else None
        c2 = r2[1] if r2 else None
        if c1 != c2:
            mismatches += 1
    out["hier_dda"] = dict(
        rays=n_bench, empty_blocks=empty_blocks,
        total_blocks=len(rock.block_count), contact_cell_mismatches=mismatches,
        plain_ms_per_ray=round(t_plain / n_bench * 1000, 4),
        fast_ms_per_ray=round(t_fast / n_bench * 1000, 4),
        speedup=round(t_plain / t_fast, 3) if t_fast else None)
    with open("../results/e_hier_dda.json", "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
