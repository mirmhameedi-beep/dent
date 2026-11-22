"""PART C supplement: bond-graph components vs VISUAL (6-connectivity)
components. Model A's `components()` cuts at SEVERED BONDS; the renderer
(isosurface of the density field) does not know about bonds. A crater whose
walls are bond-severed but spatially adjacent is still ONE visible object.
This distinction matters for every Part C claim about connected geometry."""
import json
import pickle
import sys

import modelA_stage03 as A
import maprim_rock as M
from modelA_stage03 import _NEIGH6, vkey

sys.modules.setdefault("s03_rock", A)


class DictUnpickler(pickle.Unpickler):
    """Older state pickles contain JDict/JSet instances pre-dating the
    __reduce__ patch; map them to plain builtins (journal not needed for
    read-only audits)."""
    def find_class(self, module, name):
        if name == "JDict":
            class JD(dict):
                def __init__(self, *a):
                    super().__init__(*a)
                    self.journal = {}
            return JD
        if name == "JSet":
            class JS(set):
                def __init__(self, *a):
                    super().__init__(*a)
                    self.journal = {}
            return JS
        return super().find_class(module, name)
import __main__
from streams import HistStream, HostileStream
__main__.HistStream = HistStream
__main__.HostileStream = HostileStream


def visual_components(rock):
    """Plain 6-connected components over live cells (bonds ignored) - what
    an isosurface renderer effectively shows as separate blobs."""
    L = rock.L
    seen = set()
    comps = []
    dens = rock.density
    for start in sorted(dens):
        if start in seen:
            continue
        comp = {start}
        seen.add(start)
        stack = [start]
        while stack:
            c = stack.pop()
            for dx, dy, dz in _NEIGH6:
                n = (c[0] + dx, c[1] + dy, c[2] + dz)
                if n in dens and n not in seen:
                    seen.add(n)
                    comp.add(n)
                    stack.append(n)
        comps.append(comp)
    return comps


def audit_partition(name, comps, rock):
    dfix = rock.dfix
    ISO = A.DENS_ISO * dfix
    comps2 = sorted(comps, key=len, reverse=True)
    main = comps2[0]
    main_mass = sum(rock.density[c] for c in main)
    main_has_iso = any(rock.density[c] >= ISO for c in main)
    rfrags = [c for c in comps2[1:] if any(rock.density[x] >= ISO for x in c)]
    return dict(state=name, n_components=len(comps2),
                largest_cells=len(main),
                largest_mass_legacy=main_mass / dfix,
                largest_has_iso_visible=main_has_iso,
                visible_fragment_count=len(rfrags),
                visible_fragment_mass_legacy=sum(
                    rock.density[c] for comp in rfrags for c in comp) / dfix,
                largest_share_of_field=round(len(main) / max(1, len(rock.density)), 4))


def main():
    out = {"note": "bond-graph vs visual partition on identical states"}
    for nm in ("D1_bores", "D2_fragments", "D3_hostile"):
        with open(f"../renders/state_{nm}.pkl", "rb") as f:
            d = DictUnpickler(f).load()
        rock = A.RockDensity.__new__(A.RockDensity)
        rock.__dict__.update(d)
        # JDict already materialised? these rocks were MaprimRock -> density
        # is a JDict; code below treats them as dicts, which is fine.
        bond = rock.components()
        vis = visual_components(rock)
        out[nm] = dict(
            bond=audit_partition(nm + "/bond", bond, rock),
            visual=audit_partition(nm + "/visual", vis, rock))
        print(nm, "bond comps", out[nm]["bond"]["n_components"],
              "| visual comps", out[nm]["visual"]["n_components"], flush=True)
    with open("../results/c_visual_partition.json", "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("wrote results/c_visual_partition.json")


if __name__ == "__main__":
    main()
