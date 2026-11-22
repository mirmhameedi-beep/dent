# DENT — Impact Coordinate Contract v3 (Stage 0.2 evidence-backed)

Status: proposal validated in scratch (`/tmp/dent-poc/`); NOT implemented in product.

## C1. The client sends a RAY, never a point

Request payload (proposed `/v2` tap):

```
{
  "uuid": "<client-generated UUIDv4>",
  "ray_origin":  [x, y, z],      // rock-local, canonical rock frame
  "ray_dir":     [dx, dy, dz],   // unit, rock-local; client normalises
  "geom_epoch":  N               // advisory: last damage-field version the
                                 // client rendered (for UI/telemetry only)
}
```

Measured evidence (s02_coords.py, `out/s02_coords_results.json`):
- The same screen anchor resolved from 6 view directions hit 6 different
  cells — only the ray identifies the real target.
- `two_versions` — a stale client (older epoch) sending the same ray:
  the server re-resolved against CURRENT geometry and both taps landed on the
  current surface. `geom_epoch` is informational; it never feeds geometry.
- `miss_rejected` — a ray that misses is rejected and the state hash is
  byte-identical before/after. The engine never reuses the last impact point.

## C2. Server-side resolution is the ONLY authority

The server resolves `ray ∩ current-surface` on the authoritative damage state.
Client-side material coordinates (tri, barycentric) are NEVER accepted as
placement authority (a stale client's coordinate may point into air or into
a long-gone surface). The server MAY log the client's advisory `tri/bary` for
analytics. Stale-epoch clients get a fresh delta after acceptance.

## C3. Rotation / viewing

Rays are expressed in the rock's canonical frame. Clients transform screen
rays by the inverse of the rock's view rotation (orbit only, no rock
translation). Verified: 6-direction rotation table resolves distinct,
correct cells.

## C4. Repeated taps in a crater (measured)

Crater-floor depth along one ray, L=72, same anchor (s02_coords):
taps 1 / 100 / 300 / 600 / 1000 accepted → depth 0 / 1.543 / 4.226 / 8.997 /
15.407 cells. Each tap resolved the CURRENT floor, not the original surface.
At 1,285 accepted taps the ray bores through; every later same-ray tap is
rejected (`bore_through_result: rejected:miss_rejected`).

## C5. Interior and fragment hits

- Cavity interior: a ray entering the carved mouth struck a recessed cell
  18.489 cells below the pristine surface (s02_cavity).
- Fragments: 1-cell hit checks resolve against the fragment's own cells
  (fracture set: up to 1,452 single-cell fragments). Larger fragments, when
  they exist, are hit identically — they are ordinary solid cells.

## C6. Reference frame precision

- Canonical frame: origin = rock bbox min of the canonical mesh; world-fixed.
- All engine geometry in int32 fixed point, FIX = 65,536 (1/65536 world units).
- Distances: `sqrt(a²+b²+c²)` explicitly — NOT `hypot` (V8's hypot is a
  different algorithm; 1-ulp differences flip long-run float fatigue buckets).
- Rounding: round-half-even to int (Python `round()` / JS `rhe`) — contract.

## C7. Golden-fixture parity (PROVEN, measured)

`out/s02_fixture.json` — initial states, `s02_gfix.py` ↔ `s02_gfix.js`:
identical final density map, identical 69 severed bonds at N=130, identical
bond-damage maps (51 entries), float fatigue accumulators bit-identical
(IEEE-754) across N=1..500. Canonical state hash at N=130:
`d7b8b605d03e8c54f4f4d224` — EQUAL in Python and JS.
Swift must implement the same contract and pass the identical fixtures
(pending — no Swift run available in this environment).

## C8. Known limitations / open items

- Bond keys assume vkey < 2^24 → lattice L ≤ 224 is safe (L=176 validated).
- `s02_lifecycle` Phase F's final interior probe returned None (bore-through
  of its probe ray), so interior behaviour is evidenced by s02_cavity (which
  succeeded), not by the lifecycle script.
- Fracture and per-tap damage constants are order-dependent for clustered
  bursts: parallel processing must respect the PAR2 finding (see report §3.6).
