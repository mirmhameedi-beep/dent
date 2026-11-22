"""Smoke test for maprim_rock: construction + resolver vs independent reference."""
import json
import math
import random
import sys
import time

import modelA_stage03 as A
import maprim_rock as M


def load():
    rock = M.MaprimRock(M.load_pristine(), N=20000, reserve_frac=0.02)
    return rock


def main():
    rock = load()
    dens_sum = sum(rock.density.values())
    info = dict(
        cells=len(rock.density),
        cells_ok=len(rock.density) == 151553,
        dens_sum_legacy=dens_sum / rock.dfix,
        dens_sum_ok=dens_sum == 34816588 * rock.dfix,
        M0=rock.M0, Mr=rock.Mr, q_tap=rock.q_tap,
        q_legacy=rock.q_legacy,
    )
    print(json.dumps(info, indent=1))

    rng = random.Random(4242)
    cx = rock.origin + rock.span / 2

    # 1) ref_trilerp vs engine trilerp_density on 500 random points
    maxdiff = 0.0
    for _ in range(500):
        x = rng.uniform(rock.origin - 0.1, rock.origin + rock.span + 0.1)
        y = rng.uniform(rock.origin - 0.1, rock.origin + rock.span + 0.1)
        z = rng.uniform(rock.origin - 0.1, rock.origin + rock.span + 0.1)
        a1 = rock.trilerp_density(x, y, z)
        a2 = M.ref_trilerp(rock.density, rock.L, rock.cs, rock.origin,
                           x, y, z, rock.dfix)
        maxdiff = max(maxdiff, abs(a1 - a2))
    info["trilerp_ref_max_absdiff"] = maxdiff

    # 2) resolver vs reference on rays: mixed directions, origin outside
    #    (radius 1.6*span) aimed near centre with jitter; plus axis rays
    def make_dir(tx, ty, tz):
        ln = math.sqrt(tx * tx + ty * ty + tz * tz)
        return (int(tx / ln * A.FIX), int(ty / ln * A.FIX), int(tz / ln * A.FIX))

    rays = []
    for _ in range(120):
        # random direction, origin on a sphere shell around the rock
        ux = rng.uniform(-1, 1); uy = rng.uniform(-1, 1); uz = rng.uniform(-1, 1)
        ln = math.sqrt(ux * ux + uy * uy + uz * uz) or 1.0
        r = rock.span * 1.5
        o = ((cx + ux / ln * r) * A.FIX, (cx + uy / ln * r) * A.FIX,
             (cx + uz / ln * r) * A.FIX)
        tgt = (cx + rng.uniform(-0.6, 0.6), cx + rng.uniform(-0.6, 0.6),
               cx + rng.uniform(-0.6, 0.6))
        dx, dy, dz = tgt[0] - o[0] / A.FIX, tgt[1] - o[1] / A.FIX, tgt[2] - o[2] / A.FIX
        rays.append((o, make_dir(dx, dy, dz)))
    for ax in range(3):
        for s in (1, -1):
            d = [0, 0, 0]; d[ax] = s
            o = [0, 0, 0]; o[ax] = (cx - s * rock.span * 1.5) * A.FIX
            rays.append((tuple(o), tuple(int(d[i] * A.FIX) for i in range(3))))

    agree = 0
    disagree = []
    errs = []
    t0 = time.perf_counter()
    for orig, d in rays:
        re = M.first_iso_reference(rock, orig, d)
        reng = M.resolve_iso(rock, orig, d)
        ev = reng["verdict"] if reng else "miss"
        rv = re["verdict"]
        if ev == "hit" and rv == "hit":
            # compare crossing positions in cell units
            pe = reng["point"]; pr_m = re["t"]
            # reference reports t along unit dir from same origin; compare t
            dt_cells = abs(reng["t"] - re["t"]) / rock.cs
            errs.append(dt_cells)
            if dt_cells <= 0.15:
                agree += 1
            else:
                disagree.append((re["t"], reng["t"], dt_cells))
        elif ev == rv:
            agree += 1
        else:
            disagree.append((rv, ev, None))
    dt = time.perf_counter() - t0
    n_hit_agree = len(errs)
    info["rays"] = len(rays)
    info["verdict_or_pos_agree"] = agree
    info["disagree"] = disagree[:10]
    info["hit_dt_cells_max"] = max(errs) if errs else None
    info["hit_dt_cells_mean"] = (sum(errs) / len(errs)) if errs else None
    info["bench_s_per_ray"] = dt / len(rays)
    print(json.dumps(info, indent=1))
    with open("../results/smoke_test.json", "w") as f:
        json.dump(info, f, indent=1, default=str)


if __name__ == "__main__":
    main()
