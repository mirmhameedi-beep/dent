"""PART F — original initial-rock reconstruction.

`s01_c.py` (the Stage 0.1 scanline voxelizer) is NOT in the repository or any
git ref (verified: all heads, all refs/pull/* heads searched for
`class ModelC`). However the Stage 0.3 history checkpoints pickle the full
RockDensity object, which includes `occ_init` — the exact binary occupancy
bytearray produced by s01_c.ModelC — and `boundary_init`.

The pristine initial state is therefore reconstructed EXACTLY by:
  density[(i,j,k)] = round(DENS_MAX * mat.density_var(i,j,k)) * dfix  for occ cells
followed by the identical `_cover(cover_iters=3)` relax used by the
constructor (scripts/s03_rock.py:134-138, cover_iters default=3,
MaterialField seed=7, density_var pure in position).

Verification targets from evidence (stage-0.3/results/s03_calib2_results.json):
  cells0 = 151,553   dens_sum0 = 34,816,588 (legacy units)
"""
import pickle
import sys

sys.path.insert(0, "/tmp/dent-stage03/stage-0.3/scripts")
sys.path.insert(0, "/tmp/dent-poc/model-a-prime/src")
import s03_rock as A
import streams  # noqa: F401 (pickle shims)
import __main__
__main__.HistStream = streams.HistStream
__main__.HostileStream = streams.HostileStream

CKPT = "/tmp/dent-stage03/stage-0.3/histories/B_distributed/state_10000.pkl"


def load_ckpt():
    with open(CKPT, "rb") as fh:
        rock, stream = pickle.load(fh)
    return rock, stream


def reconstruct_pristine(ref_rock):
    p = A.RockDensity.__new__(A.RockDensity)   # bypass __init__/s01_c import
    p.L = ref_rock.L
    p.cs = ref_rock.cs
    p.origin = ref_rock.origin
    p.span = ref_rock.span
    p.dfix = ref_rock.dfix
    p.mat = ref_rock.mat
    p.occ_init = ref_rock.occ_init
    p.boundary_init = ref_rock.boundary_init
    p.density = {}
    p.fatigue = {}
    A.RockDensity._init_density(p)
    n_raw = len(p.density)
    s_raw = sum(p.density.values()) / p.dfix
    A.RockDensity._cover(p, 3)
    return p, n_raw, s_raw


def main():
    out = {"source_ckpt": CKPT}
    rock, stream = load_ckpt()
    out["occ_occupied"] = sum(rock.occ_init)
    out["occ_len"] = len(rock.occ_init)
    out["boundary_init"] = len(rock.boundary_init)
    p, n_raw, s_raw = reconstruct_pristine(rock)
    cells = len(p.density)
    dens_sum = sum(p.density.values()) / p.dfix
    # integer legacy sum (each cell is an integer multiple of dfix)
    dens_sum_int = sum(v // 65536 for v in p.density.values())
    frac = sum((v % 65536) for v in p.density.values()) / 65536.0
    out.update(reconstructed_cells_raw=n_raw, reconstructed_dens_sum_raw=s_raw,
               reconstructed_cells=cells, reconstructed_dens_sum_int=dens_sum_int,
               reconstructed_dens_sum_frac=frac,
               __target_cells0=151553, __target_dens_sum0=34816588,
               cells_match=cells == 151553,
               dens_sum_match=dens_sum_int == 34816588)
    # strongest verification: pristine reconstruction must equal the 10k-tap
    # checkpoint cell-for-cell EXCEPT where taps modified cells
    dens10 = rock.density
    same = sum(1 for c, v in p.density.items() if dens10.get(c) == v)
    diff = sum(1 for c, v in p.density.items() if dens10.get(c) != v)
    only10k = len(set(dens10) - set(p.density))
    out["cells_equal_ckpt"] = same
    out["cells_diff_ckpt"] = diff
    out["cells_only_in_ckpt"] = only10k
    # independent digest
    import hashlib
    h = hashlib.sha256()
    for c in sorted(p.density):
        h.update(f"{c}:{p.density[c]}".encode())
    out["pristine_state_sha256"] = h.hexdigest()
    with open("/tmp/dent-poc/model-a-prime/results/f_initial_rock.json", "w") as f:
        import json
        json.dump(out, f, indent=1, default=str)
    print({k: v for k, v in out.items() if not k.startswith("__")})


if __name__ == "__main__":
    main()
