"""DENT Stage 0.3 — RENDERS: milestone visual states for the 5 histories +
the terminal-completion pair + pristine reference.

Uses the RESUMABLE history snapshots (state_<acc>.pkl) and renders:
  front / 3-4 view per history x milestone (MT extraction, ISO=120)
  close-ups for concentrated/clustered/adaptive craters
  terminal: before-billionth vs after (complete disintegration) at N*=20k
  pristine reference at L=72 for direct comparison.

Output: out/s03_states/*.png ; out/s03_render_manifest.json
"""
import json, os, pickle, sys, time

sys.path.insert(0, '.')
from common import gen_rock2
import s03_rock as R3
import s03_hist as _SH  # for unpickling: HistStream was saved as __main__.HistStream
sys.modules['__main__'].HistStream = _SH.HistStream
import s02_mt as MT
import s02_render as RD

OUT = "out/s03_states"
FORCE = os.environ.get("FORCE") == "1"  # incremental by default: skip existing PNGs
HIST = ["A_concentrated", "B_distributed", "C_clustered", "D_edge", "E_adaptive"]
MILES = [10000, 100000, 1000000, 10000000, 20000000, 30000000, 60000000]
CLOSE = {"A_concentrated": ((0.35, 0.30, 0.0), 2.6), "C_clustered": None,
         "E_adaptive": None}


def load(pkl):
    with open(pkl, "rb") as f:
        rock, hist_stream = pickle.load(f)
    rock._mat_cache = {}
    return rock


def render(rock, name, close=None):
    mv, mn, mt = MT.extract_mt(rock)
    wv = [(round(x * 65536), round(y * 65536), round(z * 65536)) for x, y, z in mv]
    RD.render_mesh(wv, mt, f"{OUT}/{name}_front.png", view=(0.35, -0.35, 0.88),
                   zoom=1.0)
    RD.render_mesh(wv, mt, f"{OUT}/{name}_34.png", view=(0.62, 0.5, 0.7), zoom=1.0)
    if close:
        tgt, zoom = close
        RD.render_mesh(wv, mt, f"{OUT}/{name}_close.png", view=(0.35, -0.25, 0.9),
                       zoom=zoom, target=tgt, size=460)
    return dict(verts=len(mv), tris=len(mt))


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = []
    # pristine at L=72 for direct comparison
    if FORCE or not os.path.exists(f"{OUT}/ALPHA_pristine_front.png"):
        verts0, tris0 = gen_rock2(48)
        rock0 = R3.RockDensity(verts0, tris0, lattice=72, dfix=65536)
        manifest.append(dict(name="ALPHA_pristine", **render(rock0, "ALPHA_pristine")))
        print("pristine rendered", flush=True)
    for h in HIST:
        for m in MILES:
            pkl = f"out/s03_hist/{h}/state_{m}.pkl"
            name = f"{h.split('_')[0]}_{m}"
            if not os.path.exists(pkl):
                continue
            if not FORCE and os.path.exists(f"{OUT}/{name}_front.png"):
                print("skip existing", name, flush=True)
                continue
            rock = load(pkl)
            close = CLOSE.get(h)
            if close and m < 100000:
                close = None
            try:
                info = render(rock, name, close)
                manifest.append(dict(name=name, milestone=m, hist=h, **info))
                print(name, info, flush=True)
            except Exception as e:
                manifest.append(dict(name=name, error=repr(e)))
                print("render fail", name, repr(e), flush=True)
    # terminal pair at N*=20000 (mechanism demo; scale-independent path)
    try:
        import s03_complete as CP
        import random, hashlib
        rock = CP.build_rock(20000)
        eng = CP.CompletionEngine(rock, 20000)
        rng = random.Random(31337)
        CP.stream_tap(eng, rng, 19999, "term")
        k = 0
        while eng.accepted < 19999 and k < 40000:
            tgt = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6))
            vd = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.5, 1.1))
            eng.submit(hashlib.sha256(f"t{k}".encode()).hexdigest(), tgt, vd); k += 1
            eng.process_pending()
        # safe-stop: top up with fixed rays until the NEXT accepted tap will be #20000
        info = dict(name="TERMINAL_before")
        info.update(render(rock, "TERMINAL_before"))
        manifest.append(info)
        cells_before = len(rock.density)
        # final accepted tap
        while not eng.completed and eng.accepted == 19999:
            tgt = (rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5))
            vd = (rng.uniform(-0.6, 0.6), rng.uniform(-0.6, 0.6), rng.uniform(0.5, 1.1))
            eng.submit(f"final-{k}", tgt, vd); k += 1
            eng.process_pending()
        info = dict(name="TERMINAL_after", cells_before=cells_before,
                    cells_after=len(rock.density), completed=eng.completed,
                    manifest=(eng.manifest or {}))
        info.update(render(rock, "TERMINAL_after"))
        manifest.append(info)
        print("terminal pair done", len(rock.density), eng.completed, flush=True)
    except Exception as e:
        print("terminal fail", repr(e), flush=True)
    json.dump(manifest, open("out/s03_render_manifest.json", "w"), indent=1)
    print("renders done", flush=True)


if __name__ == "__main__":
    main()
