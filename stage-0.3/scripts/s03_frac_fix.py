"""Rerun S6/S7/S8 with the fixed dispatch (S6 = all-weakened-region taps,
S7 = distributed, S8 = 2000 concentrated then distributed)."""
import json, os
import s03_frac2 as F

out = json.load(open('out/s03_frac2_results.json'))
# invalidate the known-bad S6/S8 rows produced by the shared-dispatch bug
out = [r for r in out if r.get("scenario") not in ("S6", "S7", "S8")
       or "error" in r]
for s, grains in ((6, (True, False)), (7, (True, False)), (8, (True, False))):
    for grain in grains:
        try:
            r = F.run_scenario(s, grain)
        except Exception as e:
            r = dict(scenario=f"S{s}", grain=grain, error=repr(e),
                     name=F.S_NAMES[s-1])
        r["name"] = F.S_NAMES[s-1]
        r["fixed_dispatch"] = True
        out.append(r)
        print(json.dumps(r), flush=True)
        json.dump(out, open('out/s03_frac2_results.json', 'w'), indent=1)
print("frac2 fix done", flush=True)
