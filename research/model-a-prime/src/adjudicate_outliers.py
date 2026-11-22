"""PART A follow-up: adjudicate the rare engine-vs-reference disagreements
(3 rays with err > 0.1 cells) at finer reference resolution, and decide
which side is right (engine crosses exact ISO; reference may skip a thin
feature between 0.05-cell samples)."""
import math
import random

import modelA_stage03 as A
import maprim_rock as M
import expA_surface as EA
import streams
from streams import ray_into


def fine_reference(rock, orig, d, step_cells=0.002, bisect_iters=50):
    FIX = A.FIX
    ln = math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) or 1
    ux, uy, uz = d[0] / ln, d[1] / ln, d[2] / ln
    px, py, pz = orig[0] / FIX, orig[1] / FIX, orig[2] / FIX
    cs = rock.cs
    step = cs * step_cells

    def f(t):
        return M.ref_trilerp(rock.density, rock.L, rock.cs, rock.origin,
                             px + t * ux, py + t * uy, pz + t * uz, rock.dfix)

    prev_t = step / 2
    prev_v = f(prev_t)
    t = prev_t + step
    while t < rock.span * 4.0:
        v = f(t)
        if v >= A.DENS_ISO:
            lo_, hi_ = prev_t, t
            # recovery: walk BACK to find the bracket start when prev is
            # already >= ISO (crossing inside the previous bracket)
            if prev_v >= A.DENS_ISO:
                return dict(verdict="ambiguous_start", t=None)
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


def crossings_profile(rock, orig, d, t0, t1, n=400):
    FIX = A.FIX
    ln = math.sqrt(sum(c * c for c in d)) or 1
    u = tuple(c / ln for c in d)
    px, py, pz = orig[0] / FIX, orig[1] / FIX, orig[2] / FIX

    def f(t):
        return M.ref_trilerp(rock.density, rock.L, rock.cs, rock.origin,
                             px + t * u[0], py + t * u[1], pz + t * u[2],
                             rock.dfix)
    xs = [t0 + (t1 - t0) * i / (n - 1) for i in range(n)]
    vs = [f(t) for t in xs]
    # count ISO crossings
    runs = []
    in_iso = False
    for x, v in zip(xs, vs):
        if v >= A.DENS_ISO and not in_iso:
            runs.append(["enter", x])
            in_iso = True
        elif v < A.DENS_ISO and in_iso:
            runs.append(["exit", x])
            in_iso = False
    return runs, max(vs), min(vs)


def main():
    out = []
    prist = M.load_pristine()

    # reproduce D2_fragments state exactly as expA did
    rock = M.MaprimRock(prist, N=20000, debris_policy="hold")
    rock.alpha = rock.q_legacy / 15.33
    st = streams.HistStream(rock, "C_clustered", seed=4242)
    launched = 0
    while rock.s["taps"] < 6000 and launched < 40 * 6000:
        tgt, vd = st.source()
        orig, d = ray_into(rock, tgt, vd)
        r = rock.tap_transaction(orig, d, use_iso_ray=False)
        launched += 1
        if r.get("ok"):
            st.record(r["hit"])
    rng = random.Random(777)
    cx = rock.origin + rock.span / 2
    dens = rock.density
    cells = list(dens)
    lc = sorted([c for c in cells if dens[c] // rock.dfix < 200],
                key=lambda c: dens[c])
    worst = None
    for _ in range(300):
        c = rng.choice(lc[:len(lc) // 2 + 1])
        tgt = tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))
        vd = tuple(tgt[i] - cx + rng.uniform(-0.1, 0.1) for i in range(3))
        orig, d = ray_into(rock, tgt, vd)
        ref = M.first_iso_reference(rock, orig, d)
        new = M.resolve_iso(rock, orig, d)
        if new is not None and ref["verdict"] == "hit":
            err = abs(new["t"] - ref["t"]) / rock.cs
            if err > 0.1 and (worst is None or err > worst["err"]):
                worst = dict(err=err, orig=orig, d=d, t_ref=ref["t"],
                             t_new=new["t"])
    if worst is None:
        print("no outlier reproduced")
        return
    orig, d = worst["orig"], worst["d"]
    fine = fine_reference(rock, orig, d)
    # reference at 0.05 cells again (same as battery)
    rough = M.first_iso_reference(rock, orig, d)
    # profile the crossings between the two candidate crossings
    t_lo = min(worst["t_ref"], worst["t_new"],
               fine.get("t") or min(worst["t_ref"], worst["t_new"])) - 0.5
    t_hi = max(worst["t_new"], worst["t_ref"],
               fine.get("t") or max(worst["t_new"], worst["t_ref"])) + 0.5
    runs, vmax, vmin = crossings_profile(rock, orig, d, t_lo, t_hi)
    import json as _j
    rec = dict(err_cells=worst["err"],
               t_ref_0_05=worst["t_ref"], t_engine=worst["t_new"],
               t_ref_0_002=fine.get("t"), fine_verdict=fine.get("verdict"),
               t_rough_0_05=rough.get("t"),
               iso_runs_between=[(k, round(x, 6)) for k, x in runs],
               field_max=round(vmax, 3), field_min=round(vmin, 3),
               engine_is_right_if_fine_disagrees_with_rough=None)
    if fine["verdict"] == "hit":
        rec["verdict"] = dict(
            err_engine_vs_fine=abs(worst["t_new"] - fine["t"]) / rock.cs,
            err_rough_vs_fine=abs(worst["t_ref"] - fine["t"]) / rock.cs)
    print(_j.dumps(rec, indent=1))
    out.append(rec)
    with open("../results/a_outlier_adjudication.json", "w") as f:
        _j.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
