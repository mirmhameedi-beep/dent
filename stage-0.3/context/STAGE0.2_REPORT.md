# DENT — STAGE 0.2 TECHNICAL REPORT
## Deep Physical Simulation, Deformable Rock Architecture and Future Experience Foundations

Status: isolated scratch experiments only. Zero changes to the Dent repository,
production database, Railway configuration, or Git history. All work in
`/tmp/dent-poc/` (scripts, logs, JSON), mirrors in `/workspace/s02_data/` and
`/workspace/s02_images/`.

Environment (measured, scratch machine — NOT Railway capacity):
Python 3.12.14, Node.js 22.23.5, 5 vCPU, 6 GB RAM, no new dependencies.
Some long runs executed concurrently; per-tap timings carry ±10–20% noise from that.

Classification: measured = from a completed run here; derived = computed from
measured values; estimated = reasoned, not measured; unknown = no evidence.

---

## 1. Executive recommendation

**Adopt the sparse-voxel density-field rock (Model C lineage) with a bond-lattice
fracture layer, server-authoritative ray resolution, marching-tetrahedra (MT)
extraction, and the outbox pipeline proven in Stage 0.** Stage 0.2 upgrades:

1. The damage model is now genuinely physical: dynamic density, per-cell
   material variation (hardness/toughness/density variation), bond damage,
   fatigue, stress transfer, crumble severing — producing **natural,
   non-prescribed** crater growth, interior exposure, edge loss, crack
   clusters up to 1,524 cells, cascading collapse and full natural
   disintegration under distributed load.
2. **A measured fundamental conflict**: at constants chosen for a visible
   per-tap dent, distributed load destroys the rock after **~2.3 M accepted
   taps** (measured depletion curve) — ~0.23% of the one-billion target.
   Scaling all constants down by α = 2.3e-3 to fit 1e9 makes the per-tap
   effect sub-integer (proven: a plain integer accumulator **swallows every
   tap** — zero depletion in 59k taps). Resolutions require either
   fixed-point density (~×4096) with α-calibrated constants (early taps then
   have no visible per-tap effect — they accumulate), or a founder-approved
   "regolith cushion"/hardening rule that reduces per-tap damage as the
   counter grows. This is decision D1 (founder).
3. Python/JS determinism is now **bit-exact** on golden fixtures (state hash
   `d7b8b605d03e8c54f4f4d224`, N = 1..500) under contract v3 rules. Swift
   parity remains untested (unknown).
4. Parallelism verdict (measured): pre-resolved "parallel batch" application
   **never** equals sequential re-resolution; burst order matters when anchor
   separation ≤ 1 cell. Server processing stays strictly sequential per
   transaction; geographic sharding requires dirty-region disjointness.
5. Full-engine recovery from packed snapshots is **exact at all tested
   resolutions** (L=72/96/128/176; hash equality verified post-damage).

Recommended operating point (derived, founder-approvable): L=96 server,
L=72 for initial rollout (memory 146 vs 62 MB, snapshot 1.8 vs 0.76 MB),
MT rendered client-side from server snapshots + local deltas.

## 2. Stage 0 and Stage 0.1 findings carried forward (verified)

- Production web = Canvas 2D, no deformable 3D geometry (verified).
- iOS = SceneKit sphere + dent marks (verified).
- Stage 0 spatial model: concentrated vs distributed histories → different
  rocks (re-verified here at L=72, `REPORT_equal10k.png`).
- Model A (surface shell) cannot make real interior surfaces (stands).
- Model B (remeshing) partial material removal only (stands).
- Model C (voxels) real removal + interior + fragmentation (stands; Stage 0.2
  upgrades it: density veil + bond-lattice fracture + MT extraction).
- Stage 0.1's 1,138-voxel fragment was an engineered cut — Stage 0.2 adds
  **natural cascade** collapse (no prescribed cuts anywhere in 0.2 scripts).
- Outbox + staged processing + epoch snapshots (Stage 0 Exp E) — stands.
- Python/JS parity — upgraded to bit-exact at float level (contract v3).
- Damage order-dependence — confirmed and now precisely bounded (PAR2).

Corrections applied this stage (each measured):

| # | Prior claim | Resolution |
|---|---|---|
| 1 | "12,000 centre depth" vs "8,000 saturation" | SAT = 8,000 accumulator units (int16-safe); measured `maxdepth = 8000` exactly (exp_d log). "12,000" was a unit slip: SAT×K_DISP/FIX = 0.244 world = **12.2 %** of the 2.0-diameter reference — a percentage, misread as depth. |
| 2 | Diameter/radius + crevice-gap unit mismatch (0.5 units vs "5 cells") | Not re-derivable from Stage 0.1 artifacts (documentation-level). Stage 0.2 crevices are defined in cells (L=72): FR3 gap cells [(52,40,49),(52,40,50),(52,41,46)]. Unresolved-minor; superseded by cell-defined Stage 0.2 tests. |
| 3 | Surface-cell count 230k vs 824k | 4π(256)² ≈ 823,550 is the spherical shell *face count*; a voxel rock surface occupancy is 1–2× that at L=512. No L=512 run performed (memory cost): actual L=512 occupancy = unknown; at L=176 measured 2,181,210 solid cells (full volume, not shell). |
| 4 | 2D SDF vs 3D interior evidence | Stage 0.2 adds real 3D interior proof: recessed cavity wall struck 18.489 cells below pristine surface; interior cells crumble and vanish (s02_cavity, `interior_damage_confirmed: true`). |
| 5 | Python/JS equality vs untested Swift | Parity improved to bit-exact (contract v3); Swift remains untested/unknown. |
| 6 | "13,826 vertices" vs proposed 50–100k | 13,826 = `gen_rock2(48)`. Measured family: gen_rock2(96) → 55,298 verts. Canonical 50–100k target ≈ subdivision 90–130. Density decision deferred until contract freeze. |
| 7 | Engine `vkey/vunkey` bug (found this stage) | The +1 key offset broke the extreme +x face (97 cells at L=72 decoded to i=−1), corrupting stress propagation there. Fixed; all runs restarted; FR/lifecycle qualitative results unchanged. Snapshot round-trip now hash-exact at all L. |

## 3. Physical material model (new in Stage 0.2)

Measured basis: per-cell **density** (0..240 int), **hardness**, **toughness**,
**density variation** (integer value-noise fields, `s02_rock.py::MaterialField`).
Rules (contract v3, bit-exact in Python+JS):
- R1 carve: `d -= K_COMPRESS · smoothstep(1 − dist/R_IMPACT) / hardness`
- R2 crumble: `density < DENS_FAIL` → cell leaves the solid map
- R3 bond damage near flaws (reduced density, fatigue > 400, sibling damage)
- R4 sever at `damage ≥ BOND_STRENGTH · toughness`
- R5 severed bond → stress transfer to flawed sibling bonds (bounded worklist)
- R6 all arithmetic integer/fixed-point under FIX = 65,536; half-even rounding;
  distances via explicit `sqrt(a²+b²+c²)` (hypot's 1-ulp drift breaks parity)

## 5. Impact lifecycle results (measured)

### A. Initial impact
One tap (L=96): depth_cells 0.01; 1.47 ms cold, ~0.4 ms warm. Sub-pixel at
340/680 px under billion-scale calibration; currently a faint dimple.

### B. Repeated same-location impacts (decisive)
Floor depth along one ray (L=72): taps 1/100/300/600/1000 accepted → depth
0 / 1.543 / 4.226 / 8.997 / 15.407 cells. Every tap resolved the CURRENT floor
(re-resolution per impact). Bore-through: 1,285 accepted (L=72), 1,699 (L=96).
After bore-through every later same-ray tap is rejected; 200k same-ray taps →
only 1,393 accepted, rock intact elsewhere — **concentration self-limits**.

### C. Distributed (measured)
10,000 accepted distributed: 3 cells lost (of 151,553). 10,000 concentrated:
495 cells lost + visible crater. Same counters, completely different rocks
(`REPORT_equal10k.png`).

### D/E/F. Overlap, edges, cavities, fracture surfaces (measured)
- FR1 crumbling face: 1,393 taps → 1,179 severed, crack cluster 615 cells.
- FR2 edge line: 2,050 taps → 490 severed, 2 clusters (221, 63).
- FR3 crevice floor: 6,591 taps → 2,739 severed, clusters through the thin floor.
- FR4 clusters: 9,973 taps → 7,003 severed, 3 clusters (max 1,524 cells), merging.
- FR5 distributed: 17,114 taps → 9,469 severed, **36 clusters** — widespread
  natural pitting.
- FR6 weakened root: 24,000 taps → single dominant cluster (1,206) — failure
  propagates from the weakened section.
- Interior cavity wall: ray through the carved mouth hits a cell recessed
  **18.489 cells** below the pristine surface; 400 hammer taps on that interior
  cell removed it plus 12 neighbours within radius 2; 26 low-density cells
  within radius 3.

### 6. Natural fracture — what works, what doesn't
Cracks emerge as connected clusters of severed bonds; they propagate via
fatigue + stress transfer; they merge across clustered craters (FR4); they
cross thin sections (FR3); a dominant crack forms at the weakened root (FR6).
The 6-connected bond lattice makes cracks axis-aligned stair-steps rather than
continuum paths — visually acceptable in MT rendering, a known approximation.
**No multi-cell fragment naturally detached in any Stage 0.2 run** (frag_top
all 1s in FR1–FR6): separation arrives as accelerating cascade, not as chunks.
Detachment of large chunks remains unproven.

## 7. Material removal / interior exposure
Crumble removal creates real voids; newly exposed interior cells are
addressable and damageable (s02_cavity; lifecycle Phase F: 845 interior taps
accepted). Interiors render as MT iso-surfaces of the density veil
(`VS_cavity_interior_*.png`). Limitation: single iso-level veil; no strata
detail inside large cavities. Debris: fragments are single-cell; "debris
settle" presentation would be client-side ephemeral graphics (concept only).

## 8. Geometry extraction quality (measured)

| L | blocky s / tris | MT s / tris | MT local (2,197-cell box) |
|---|---|---|---|
| 72 | 0.19–0.21 s / 46,512 | 30.66 s / 114,290 | 0.83 s (36×), needs edge-face filter |
| 96 | 0.46 s / 82,180 | 69.39 s / 200,412 | (not run) |

Visual verdict: damage reads clearly at 420–560 px; voxel facets still visible
at L=72–96 (mitigations: higher server L, smooth shading — present — and later
sub-cell client displacement, est. 1–2 weeks). The visual identity (charcoal
background, warm-grey stone) is consistent across all stage renders.

## 9. One-billion completion problem (central finding)

Measured depletion curve (L=72, 151,553 cells, distributed load):

| accepted taps | cells left | depletion |
|---|---|---|
| 7,382 | 151,553 | 0.0% |
| 95,932 | 147,964 | 2.4% |
| 247,165 | 136,397 | 10% |
| 531,721 | 113,664 | 25% |
| 984,356 | 75,776 | 50% |
| 1,444,585 | 37,888 | 75% |
| (cascade) | 0 | 100% before the 3.5M cap |

Derived slope (late window): **15.23 accepted taps per cell lost**; linear
fit → 2.31 M full depletion; depleletion accelerates → estimated 2.2–2.5 M.

Calibration validations (measured):
- **C1 integer swallow**: α-scaled constants on pure-integer density → ZERO
  depletion in 59,078 taps (proven: simply shrinking constants cannot work).
- **C2 fixed-point ×4096 + α + α-scaled K_BOND**: zero cell loss in 300k taps
  (consistent with the α-scaled slope prediction of ~45 cells lost over the
  window) — but it also shows depletion is dominated by **nonlinear sever
  cascades**, not smooth carve. Cascade timing at α-scale is **unproven**
  (needs a 30–60M-tap offline soak ≈ 4–6 scratch-hours; recommended next).

Founder decision **D1** — completion policy (measured trade-off):
- (a) α-calibrated fixed-point: early dents invisible, full experience spread
  across 1e9 taps; cascade timing needs soak verification.
- (b) Keep visible per-tap dents + measured "regolith cushion" hardening:
  per-tap effect shrinks with the global counter; completion at
  min(1e9, natural exhaustion); visible policy knob, physically narrated
  (impact rubble cushions the surface — a real phenomenon).
- (c) Hybrid (a)+(b).
Final-state rule (either way): the rock ends in whatever state the actual
distribution produced; the billionth accepted tap triggers the formal end
(epoch = 1e9 snapshot + final published hash); post-completion taps rejected;
if distributed load exhausts the rock before 1e9, that is a separate product
rule (**D2**) — technical machinery supports both.

## 10–11. Resolution, storage (measured)

| L | solid cells | init RSS | snapshot B | ms/tap dist | MT extract | recovery |
|---|---|---|---|---|---|---|
| 72 | 151,553 | 62 MB | 757,777 | 0.388 | 30.66 s | 1.86 s exact |
| 96 | 357,115 | 146 MB | 1,785,587 | 0.390 | 69.39 s | 4.94 s exact |
| 128 | 842,296 | 308 MB | 4,211,492 | 0.423 | (not run) | 11.02 s exact |
| 176 | 2,181,210 | 428 MB | 10,906,062 | 0.497 | (not run) | 31.39 s exact |

Definitions: L = lattice cells across the 2.10-world bounding box. Snapshot =
sorted uint32 vkeys + uint8 densities + uint64 severed bond keys = 5 B/cell,
uncompressed (deflate est. 40–60% extra — estimated, unmeasured). Bond-damage
and fatigue maps excluded from snapshots (estimated +10–15% — unmeasured).
This is state-only storage; the tap ledger and idempotency store follow the
Stage 0 Exp F analysis (unchanged). Railway storage at L=96 fits comfortably
in the 500 MB volume (~250 epoch snapshots, uncompressed, derived).

## 12. Incremental updates and parallel-safety (measured)

PAR (single-tap pairs): all commute (no nonlinearity crossed — expected).
PAR2 (bursts at two anchors, all 12 combinations):

| burst n | sep (cells) | AB == BA | pre-resolved "parallel batch" == sequential |
|---|---|---|---|
| 5 / 25 / 100 | 0 | NO | NO |
| 5 / 25 / 100 | 1 | NO | NO |
| 5 / 25 / 100 | 3 | YES | NO |
| 5 / 25 / 100 | 6 | YES | NO |

Evidence-backed rule: two impacts may process in parallel **iff** their damage
kernels + flaw/stress propagation neighbourhoods are disjoint **and** neither
one's re-resolution surface is affected by the other's damage. Pre-resolved
batch application ≠ sequential at any separation → **rejected** for product.
Local rebuild measured: blocky dirty-box 0.003 s vs 0.211 s full (70×);
MT dirty-box 0.83 s vs 30.19 s (36×; needs a one-line patch-edge face filter —
known gap, not implemented). Delta size expected bounded by the dirty region
(estimated, unmeasured).

## 13. Impact coordinates and stale clients (measured)
Contract v3 (`coordinate_contract_v3.md`): client sends a RAY in the canonical
rock frame (+ advisory epoch); server resolves against CURRENT geometry;
client tri/bary coordinates are never placement authority; misses are rejected
with byte-unchanged state; no fallback to the last accepted point (proven:
`miss_rejected.state_unchanged = true`); bore-through → reject; two-version
convergence verified (`two_versions: both land current surface`).

## 14. Cross-platform
- Contract v3 bit-exact in Python ↔ JS (fixtures N = 1..500; hash
  `d7b8b605d03e8c54f4f4d224`).
- Production canonical mesh must be a byte-identical FILE (obj/gltf at fixed
  subdivision), not a procedural regeneration (regeneration parity is not
  guaranteed across future engine versions — contract-relevant).
- Rendering differences (lighting/materials) are explicitly allowed; geometry
  and damage state must match byte-exactly.
- Swift/SceneKit: untested (unknown). Fixture set ready for the port.

## 15. Future modularity (conceptual; nothing implemented)
Boundaries: (1) rock/damage engine; (2) tap acceptance + ledger; (3)
presentation; (4) live presence; (5) recognition; (6) sponsorship; (7)
commerce. Principle: the physical rock depends on nothing; optional modules
consume the accepted-tap event stream with their own checkpoints (Stage 0's
outbox already provides the pattern). A badge-runner outage must never block
tap acceptance; presence must never create dents.

## 16–17. Evidence index
- `/workspace/s02_images/REPORT_progression.png` — pristine → S100/S1k/S10k/S30k + interior
- `/workspace/s02_images/REPORT_fractures.png` — FR1..FR6 three-quarter views
- `/workspace/s02_images/s02/FR*_close.png` — fracture close-ups
- `/workspace/s02_images/REPORT_equal10k.png` — concentrated vs distributed
- `/workspace/s02_images/REPORT_destruction.png` — 10/25/50/75% erosion
- `/workspace/s02_images/s02/VS_cavity_interior_*.png` — interior exposure
- JSONs: `/workspace/s02_data/s02_*.json`; logs: `/workspace/s02_data/logs/`
- Scripts: `/workspace/s02_data/scripts/` (s02_*.py, s02_gfix.js, montage)
- Scratch originals: `/tmp/dent-poc/`

## 18. Remaining risks (ranked)
- **R1** — one-billion calibration end-to-end unproven (needs soak + D1).
- **R2** — no real three.js/SceneKit benchmark yet (scratch software
  rasterizer times are NOT transferable); L=96 MT mesh = 200k tris needs
  client-side LOD (est. 2–4 weeks).
- **R3** — no natural multi-cell fragment detachment yet (cascade-only).
- **R4** — Swift parity unverified.
- **R5** — MT local patch edge filter not implemented (known fix).
- **R6** — Railway production runtimes unmeasured.

## 19. Phased roadmap (content revised)
1. Feasibility — PROVEN (this evidence set).
2. Canonical asset: founder-approved DENT-2 mesh, obj/gltf byte-exchange,
   subdivision ~90–130 (50–100k verts), single material pipeline.
3. Contract v3 in backend + web ray-caster (three.js recommended; Canvas 2D
   cannot represent 3D rays).
4. Damage layer + outbox (L=96 server, L=72 rollout), Python/JS twin fixtures
   in CI.
5. Web geometry: MT client renderer + epoch deltas + local patch filter (R5).
6. iOS: Swift fixture port first, then SceneKit.
7. Scale/perf: production profiling; 30–60M-tap α-scale soak (our own).
8. Completion + disintegration (D1/D2 rules).
Gate: phases 2+ require founder decisions D1–D4.

## 20. Founder decisions
- **D1** damage-calibration policy (a)/(b)/(c) — §9.
- **D2** exhaustion-before-1e9 rule.
- **D3** permanent UUID retention (unsettled from Stage 0 — deliberately untouched).
- **D4** canonical asset approval.
- Optional: initial L (recommend 72 rollout / 96 target); debris presentation scope.

## Appendix — experiment index

| Exp | Script | Key result |
|---|---|---|
| A1–A6 | s02_fracture.py | natural cracks 63–1,524 cells; FR1–FR6 measured |
| B | s02_lifecycle.py | floor 0→16.9 cells; bore-through 1,699; final hash 9c0a22a8a1ac6e83 |
| B′ | s02_coords.py | depth table; bore-through 1,285; miss-reject; 6 views; two-version |
| C | s02_cavity.py; s02_vis.py | 18.489-cell recess; interior cell removed; V3 renders |
| D | s02_completion.py (pathological) | 200k same-ray taps → 1,393 accepted; self-limiting |
| D′ | s02_calib.py | C1 integer swallow proven; C2 fixed-point zero-loss window |
| E | Stage 0 exp_e.py (stands) | outbox + recovery proven earlier |
| F | s02_res.py | resolution/storage/recovery table (exact at all L) |
| G | s02_gfix.py/.js | bit-exact parity N=1..500; hash d7b8b605d03e8c54f4f4d224 |
| PAR/PAR2 | s02_par.py / s02_par2.py | parallel-safety rule table |
| COMP | s02_completion.py | slope 15.23 taps/cell; derived 2.31 M depletion |
| VIS | s02_vis.py | equal-10k pair; destruction curve; interior renders |
| FIX-vkey | s02_rock.py | +1 key-offset bug found and fixed; runs rerun |
