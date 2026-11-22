"""DENT Stage 0.3 — equal-tap side-by-side comparison sheets.

Builds REPORT_s03_* montages from the per-history renders in out/s03_states/
(same pristine rock, same renderer, same zoom). Re-runnable: milestones that
appear later (10M/30M/terminal) are picked up on the next invocation.

Sheets produced (front view unless noted):
  equal_10000 / equal_100000 / equal_1000000 / equal_10000000 / equal_30000000
  -> rows: pristine + histories A-E  (cols = 6, one per stage)
  terminal_pair -> before-billionth vs after (complete disintegration)
"""
import os, sys
sys.path.insert(0, '.')

import s02_montage as M

O = "out/s03_states"
OUT = "out"
# render files use the SHORT prefix: A_10000_front.png etc.
HISTS = ["A", "B", "C", "D", "E"]
HIST_NAMES = {"A": "A_concentrated (concentrated)", "B": "B_distributed (distributed)",
              "C": "C_clustered (clustered)", "D": "D_edge (edge-focused)",
              "E": "E_adaptive (adaptive)"}
MILES = [10000, 100000, 1000000, 10000000, 20000000, 30000000]


def build_equal(mile, out_name):
    panels = [f"{O}/ALPHA_pristine_front.png"]
    labels = ["pristine"]
    for h in HISTS:
        p = f"{O}/{h}_{mile}_front.png"
        if os.path.exists(p):
            panels.append(p)
            labels.append(HIST_NAMES[h])
    if len(panels) < 3:
        return False
    M.tile(panels, f"{OUT}/REPORT_s03_{out_name}.png", cols=min(len(panels), 3))
    print("  panels:", labels)
    return True


def build_terminal():
    b = f"{O}/TERMINAL_before_front.png"
    a = f"{O}/TERMINAL_after_front.png"
    if os.path.exists(b) and os.path.exists(a):
        M.tile([b, a], f"{OUT}/REPORT_s03_terminal_pair.png", cols=2)
        return True
    return False


def main():
    done = []
    names = {10000: "equal_10000", 100000: "equal_100000",
             1000000: "equal_1000000", 10000000: "equal_10000000",
             20000000: "equal_20000000", 30000000: "equal_30000000"}
    for m in MILES:
        if build_equal(m, names[m]):
            done.append(names[m])
    if build_terminal():
        done.append("terminal_pair")
    print("montages built:", done or "none yet")


if __name__ == "__main__":
    main()
