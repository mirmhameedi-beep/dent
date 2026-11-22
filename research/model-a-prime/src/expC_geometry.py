"""PART C - Inventory conservation vs visible physical rock.

Measures four SEPARATE quantities over compressed-lifetime runs on the
authentic original rock:

  A. Total material inventory   (M0 - consumed - burned; exact integers)
  B. Renderable material        (mass in components containing >=1 cell with
                                 density >= DENS_ISO; approximation: the true
                                 renderable set is defined by the trilinear
                                 field, per-cell classification is an upper
                                 bound on renderability)
  C. Hittable material          (exterior cells of renderable components -
                                 reachable by a ray that crosses the ISO field)
  D. Connected visible material (largest renderable component + renderable
                                 detached fragments)

Then an ADVERSARIAL test: hammer the smallest visible component until it
dies, and report what the ledger does (predicted: ledger stays far above Mr
while a visible object disappears -> mass guarantee is NOT a geometry
guarantee).

Also measures the silent visible->invisible pressure: mass in sub-ISO cells
inside the main component (field-visible only via interpolation, and with
the ISO resolver effectively no longer directly hittable).
"""
import json
import pickle
import random
import statistics
import time

import modelA_stage03 as A
import maprim_rock as M
import streams
from streams import ray_into
import expA_surface as EA


def milestone_run(hist="A_rot", n_target=8000, policy="hold"):
    rock = M.MaprimRock(M.load_pristine(), N=20000, debris_policy=policy)
    rock.alpha = rock.q_legacy / 15.33
    st = streams.HistStream(rock, hist, seed=4242)
    snaps = []
    milestones = {1000, 2000, 4000, 6000, 8000}
    launched = 0
    t0 = time.perf_counter()
    while rock.s["taps"] < n_target and launched < 40 * n_target:
        tgt, vd = st.source()
        orig, d = ray_into(rock, tgt, vd)
        r = rock.tap_transaction(orig, d, use_iso_ray=False)
        launched += 1
        if r.get("ok"):
            st.record(r["hit"])
        if rock.s["taps"] in milestones and \
                (not snaps or snaps[-1]["n"] != rock.s["taps"]):
            g = M.geometry_audit(rock, ledger=rock)
            g["n"] = rock.s["taps"]
            snaps.append(g)
            print("  milestone", rock.s["taps"], "B_render",
                  g["B_renderable_mass"] // rock.dfix, "D_main",
                  g["D_main_object_mass"] // rock.dfix, flush=True)
    g = M.geometry_audit(rock, ledger=rock)
    g["n"] = rock.s["taps"]
    snaps.append(g)
    wall = time.perf_counter() - t0
    return rock, snaps, wall


def dfixify(g, dfix):
    out = {}
    for k, v in g.items():
        out[k] = v / dfix if isinstance(v, int) and abs(v) > 1e7 else v
    return out


def adversarial_fragment_kill():
    """Hammer the smallest RENDERABLE fragment until it stops being visible."""
    # build a fragmented state
    rock = M.MaprimRock(M.load_pristine(), N=20000, debris_policy="hold")
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
    comps = rock.components()
    comps.sort(key=len, reverse=True)
    dfix = rock.dfix
    ISO = A.DENS_ISO * dfix

    def comp_visible(comp):
        return any(rock.density[c] >= ISO for c in comp)

    renderable = [c for c in comps if comp_visible(c)]
    if len(renderable) < 2:
        return dict(skipped="no detached renderable fragment existed "
                            "after 6000 clustered taps",
                    comps=len(comps))
    victim = min(renderable, key=len)
    v_cells = len(victim)
    v_mass = sum(rock.density[c] for c in victim)
    g0 = M.geometry_audit(rock, ledger=rock)
    # hammer it: aim rays at its cells from outside
    rng = random.Random(31415)
    dead_at = None
    taps_used = 0
    launched = 0
    while launched < 20000:
        if rock.density:
            alive_cells = [c for c in victim if c in rock.density]
        else:
            alive_cells = []
        if not alive_cells:
            dead_at = taps_used
            break
        # stop if the component is no longer renderable
        if not comp_visible(alive_cells):
            dead_at = taps_used
            break
        c = rng.choice(alive_cells)
        tgt = tuple(rock.origin + (c[i] + 0.5) * rock.cs for i in range(3))
        cx = rock.origin + rock.span / 2
        vd = tuple(tgt[i] - cx for i in range(3))
        orig, d = ray_into(rock, tgt, vd)
        rock.tap_transaction(orig, d, use_iso_ray=False)
        taps_used += 1
        launched += 1
    g1 = M.geometry_audit(rock, ledger=rock)
    comps1 = rock.components()
    comps1.sort(key=len, reverse=True)
    still_visible_frags = sum(1 for comp in comps1 if comp_visible(comp))
    return dict(
        victim_cells=v_cells, victim_mass_legacy=v_mass / dfix,
        taps_to_kill=taps_used, dead=dead_at is not None,
        before=dict(A_total=g0["A_total_inventory"] / dfix,
                    B_renderable=g0["B_renderable_mass"] / dfix,
                    D_frag_count=g0["D_visible_fragment_count"],
                    D_frag_mass=g0["D_visible_fragment_mass"] / dfix),
        after=dict(A_total=g1["A_total_inventory"] / dfix,
                   B_renderable=g1["B_renderable_mass"] / dfix,
                   D_frag_count=g1["D_visible_fragment_count"],
                   D_frag_mass=g1["D_visible_fragment_mass"] / dfix,
                   Mr=rock.Mr / dfix,
                   A_total_above_Mr=(g1["A_total_inventory"] > rock.Mr),
                   visible_component_count=still_visible_frags),
    )


def main():
    out = dict(meta=dict(purpose="PART C inventory vs visible geometry",
                         definitions=dict(
                             A="M0 - consumed - burned (exact integer ledger)",
                             B="mass in components with >=1 cell >= DENS_ISO",
                             C="exterior-cell mass of renderable components",
                             D="largest renderable component (+ renderable "
                               "fragments)"),
                         stream_note="compressed-lifetime alpha = "
                                     "q_legacy/15.33, N*=20000, authentic rock",
                         started=time.strftime("%Y-%m-%d %H:%M:%S")))
    for hist in ("A_rot", "B_distributed"):
        rock, snaps, wall = milestone_run(hist=hist)
        sn = []
        for g in snaps:
            gg = dict(g)
            for k in list(gg):
                if isinstance(gg[k], int) and abs(gg[k]) > 10**7:
                    gg[k] = gg[k] / rock.dfix
            gg["frac_invisible_of_inventory"] = round(
                gg["B_invisible_mass"] / max(1, gg["A_total_inventory"]), 5)
            gg["frac_sub_iso_in_main"] = round(
                gg["sub_iso_mass_inside_main"] / max(1, gg["A_total_inventory"]), 5)
            sn.append(gg)
        out[f"run_{hist}"] = dict(snaps=sn, wall_s=round(wall, 1),
                                  consumed_legacy=rock.consumed / rock.dfix,
                                  debris_legacy=sum(rock.debris.values()) / rock.dfix,
                                  fines_legacy=sum(rock.fines.values()) / rock.dfix)
        print(hist, "done", flush=True)
        with open(f"../renders/state_C_{hist}.pkl", "wb") as f:
            pickle.dump(rock.__dict__, f)

    print("adversarial fragment kill...", flush=True)
    out["adversarial_fragment_kill"] = adversarial_fragment_kill()
    print(json.dumps(out["adversarial_fragment_kill"], indent=1)[:1500])
    with open("../results/c_geometry.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote results/c_geometry.json", flush=True)


if __name__ == "__main__":
    main()
