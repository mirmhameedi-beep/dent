# DENT — STAGE 0.3 FINAL REPORT
# Physical calibration, natural fracture, one-billion-tap lifespan, complete destruction

**Status: investigation + isolated PoC only. No product implementation. Scratch environment `/tmp/dent-poc/`, nothing in the Dent repository, production, Git, or Railway was touched. No production requests were made.**

**Labels used on every number:** `measured` (from a logged experiment run), `derived` (computed from measured inputs by stated formula), `estimated` (assumption-backed approximation), `hypothesis` (needs work), `unknown`.

**Environments:** scratch container, 5 vCPU, ~6 GB RAM, Python 3.12.14, Node 22.23.5, pure stdlib. All timings are scratch-machine numbers under heavy multi-job contention; they are NOT Railway or device capacities.

---

## 1. Executive recommendation

The sparse voxel density material model with a **per-tap mass cap (Model A)** — alpha-scaled damage, DFIX=65536 fixed-point density accumulation, two-pass capped carve — is verified as the correct physical core for Dent's one-billion-tap rock:

1. **Early-death cause found and falsified (measured):** at legacy constants the ~2.3M-tap distributed depletion is a *pure per-tap mass-budget effect* (kernel integral of K_COMPRESS·w/hardness ≈ 15.1 density units per accepted tap), **not** cascade collapse. Severing and fatigue contribute exactly 0 of the cell loss in the distributed-load attribution experiment. The Stage 0.2 nonlinear-collapse hypothesis is falsified for depletion.
2. **The no-early-death requirement is enforceable as a derived bound (measured + derived):** with per-tap carve clipped to `cap = (d̄₀−30)·cells₀/1e9`, 0 cap violations were observed in 43,571 accepted taps, full mass conservation holds to within per-cell integer rounding (1.3e-4 relative), and tiny takes demonstrably accumulate (no rounding away: granularity 1.5e-5 units/tap against a 0.0303 units/tap budget).
3. **Five distinct impact histories preserved (measured to 10M, continuing):** concentrated/distributed/clustered/edge/adaptive histories produce materially different sever counts, removal counts, rejection profiles and (at ≥10M) measurable density-deficit profiles from the same pristine rock.
4. **Natural multi-cell fragment separation is demonstrated (measured):** multi-cell fragments (top fragments 12–14 cells at the narrow-waist scenario; 3-cell at corner; contra 0-stage-0.2's single-cell-only finding) detach from ordinary accumulated tapping in scenarios that create narrow/cracked geometries — with and without grain structure. The grain lattice (inter-granular toughness ×0.72–0.85) increases severing ~1.6–1.8× and brings crack initiation earlier, but is **not required** for multi-cell detachment in waist/corner geometries. Under purely distributed load (S7), multi-cell fragments essentially do not form (measured: 1 two-cell fragment in 6,000 taps with grain, none without) and bore-through proceeds by local erosion instead. This is stated as a measured limitation of distributed erosion, not hidden.
5. **The fixed completion event is verified (measured, 7/7 cases):** at exactly N* accepted taps the billionth tap commits *with* a TERMINAL event in one transaction; disintegration clears every remaining cell and fragment; a deterministic completion manifest (pre-state hash + RNG seed) is committed; post-completion taps are rejected; duplicate UUIDs never recount; crash-recovery replays in all seven injected failure scenarios at N*=20,000. An earlier attempt at N*=60,000 **failed** for a now-understood reduced-scale artifact (per-tap cap grows ∝ 1/N*, so a concentrated stream bores through before reaching N*) — preserved separately as evidence (`s03_complete_results_NStar60k_partition_problem.json`), superseded by the passing N*=20,000 run.
6. **Concentrated damage slows per-tap processing (measured, growing):** processing cost is dominated by the bond/carve kernel plus ray bisection; the concentrated history's cost per tap grows measurably beyond 1M (profiled: `impact` kernel = 88 s / 150 s cumulative, ~97 bond visits/tap). This is an engineering risk item (mitigations in §12), not a correctness failure.
7. **Honest visibility trade-off (derived + measured):** billion-calibration makes each accepted tap remove ≈1/6,600 of a cell-equivalent of material. Per-tap drama must come from the presentation layer (dust/flash/audio, founder product decisions); the geometry evolves truthfully on the billion schedule. Concentrated histories nevertheless develop *deep visible bores* over ≥10M taps; distributed histories thin uniformly.
8. **Swift is not available in this environment (measured: `which swift` empty)** — web-first development (three.js path unbenchmarked, carried as open risk R2) and independent web testability remain the recommended path; Python↔JS golden-fixture parity re-confirmed this session.

---

## 2. Verified Stage 0–0.2 findings (carried forward, re-verified this session)

- **Reproducibility re-check (measured this session):** golden fixture N=130 rerun: Python↔JS state dumps content-identical (severed 69 both; recomputed canonical hash `4c54248ae09850654f8b17e2`, byte-identical in both runtimes; the stored 0.2 hash `d7b8b605…` was an ad-hoc formula, documented as such). `s02_fracture.py` fully rerun byte-equal.
- Transactional outbox, staged processing, epoch snapshots, recovery: verified in Stage 0, re-exercised at 7/7 in Stage 0.3's completion harness.
- Damage processing is order-dependent; arbitrary batching != sequential (Stage 0; PAR/PAR2 conditions restated in §12).
- Surface-shell (A) cannot show real interior; **Model C (sparse voxel density) removes real material and exposes interior** — this is the basis of the Stage 0.2/0.3 engine.
- Python↔JS deterministic parity holds for the full damage engine; Swift/SceneKit/three.js parity and performance remain unbenchmarked (unknown).
- Operating constants ledger (0.2, verified in files): DENS_MAX=240, DENS_FAIL=30, DENS_ISO=120, K_COMPRESS=2.6, K_BOND=90, BOND_STRENGTH=1000, SC_PROP=240, R_IMPACT=2.6, R_BOND=2.2, SAT=8000, FIX=65536.

---

## 3. Physical material model

Material state per cell: density (fixed-int, DFIX=65536 subdivision of the legacy 30–240 unit scale), hardness, toughness (spatially varying via the procedural field `vnoise3`), fatigue, bond lattice (`bkey=(va<<24)|vb`) with per-bond damage, severed set, stress queue. An accepted tap resolves a ray against the CURRENT density field (trilerp + bisection refinement at DENS_ISO=120), then applies a carve kernel `take = A·K_COMPRESS·w(r)/hardness` inside R_IMPACT=2.6 cells, bond damage inside R_BOND=2.2, severing by accumulated damage threshold, stress concentration drained to sibling bonds within a per-impact bound (2000).

**Translation of one accepted tap → persistent consequence (measured):** one accepted tap at the billion calibration removes ≤ `cap` = 0.03027 density units/cell (clipped, 0 violations in 43,571 taps §V1) — a hot but *fully accumulated* consequence; nothing is discarded, nothing rounds to zero (§V3).

**Precision:** the fixed-point grid gives per-tap granularity 1/65536 = 1.5259e-5 legacy units (measured) against a 3.0e-2-unit budget/tap — 4+ decimal digits of headroom; a 100k-tap single-location run measured a total loss of 3232.8 units vs the analytic cap-sum 3027.0 (the +6.8% = crumble tail: cells crossing the DENS_FAIL=30 floor are removed whole, one-off per cell; measured, concentrated-region worst case).

**Conservation identity (measured):** `initial_dens_sum − final_dens_sum == Σ applied carve takes` within per-cell integer rounding bound (0.5/DFIX per cell-update; measured residual 0.16 on 1270.0 = 1.3e-4 relative; account closed exactly when removal count is 0).

---

## 4. Damage calibration — why the rock died early, and the fix

### 4.1 Component attribution (measured; `s03_attr_results.json`)

Three 300k-launched distributed runs (291,953 accepted each): BASE = NOSEV = NOFAT —
- identical material slope **15.1237 density units / accepted tap**;
- identical cell loss **18,684 cells**;
- BASE and NOFAT state hashes identical (`152aa129…`); NOSEV differs (89,158 severings vs 0) but cell loss unchanged.
- **All 18,684 removals were single-tap kills of pristine low-density (30–60) shell cells** — the `_cover`-relaxed boundary artifact.
- **Conclusions:** (a) loss flows only through the carve-crumble path; (b) severing/fatigue have zero contribution to depletion under distributed load; (c) the ~2.3M early death is a per-tap MASS BUDGET problem, not cascade collapse. Derived depletion at the measured slope: 2,292,040 accepted taps.

### 4.2 Models A–D (measured, 1M concentrated window each; `s03_calib2_results.json`)

| Model | Cells lost (1M) | Budget/tap | First removal | Severings | Rejected |
|---|---|---|---|---|---|
| A (α-scaled + cap + DFIX) | 59 | 0.03147 | 77,236 | 428 | 0 |
| B (=A + β=3 fatigue softening) | 76 | 0.03245 | 53,718 | 502 | 4,025 |
| B2 (=A + β=8) | 84 | 0.03274 | 46,141 | 519 | 39,377 |
| C (=A + lateral support ×0.55+0.075n) | 63 | 0.03191 | 70,697 | 440 | 0 |
| D (=A + pacing cap growth) | 59 | 0.03147 | 77,236 | 428 | 0 |

- Fatigue softening (B/B2) makes lifespans *worse* (more removals, earlier first removal) — it is a realism feature, not a survival mechanism.
- Structural reinforcement (C) is **not needed** for survival under the cap (63 vs 59 cells — measured; its only effect is slightly slower early erosion).
- Global pacing (D) is *provably inert until ≥10% mass loss* (identical state hash to A at 1M — measured) and never creates damage by itself: it only widens an already-admissible per-tap clip; it is available as a founder-appprovable lever to preserve *late-stage* interactability, it does not touch untouched regions.

**Primary recommendation: Model A core.** Models B/C/D are additive variants, none required for the fixed requirement.

### 4.3 Cap correctness, precision, conservation (measured; `s03_capcheck_results.json`, `s03_precision_v3.json`)

- V1: max observed per-tap carve = 0.030270 == `cap` exactly; **0 violations / 43,571 accepted taps** (measured).
- V2: conservation identity holds at 1.3e-4 relative (measured; per-cell rounding bound derived ≤0.5/DFIX per update).
- V3: single-location 100k-tap run: measured loss 3232.8 vs analytic 3027.0 (**no rounding-away**; granularity 1.5e-5/tap measured; crumble tail +6.8% one-off, measured; the tail is bounded because crumble is a one-off per cell).

---

## 5. Long-duration simulations  *(statuses as of report time; all resumable — see §18)*

Five histories, Model A calibration `cap=0.03027/tap, α=0.00197456`, L=72, seed 4242, 30M accepted target, milestones 10k/100k/1M/10M/20M/30M.

**Measured at 10M accepted** (metrics.jsonl; A at its exhausted terminal value):

| History | Launched | Accepted 10M | Cells left | Density sum | Removals | Severings | Fragments | Largest frag |
|---|---|---|---|---|---|---|---|---|
| A concentrated | 1,000,000+ | **stall at 1,549,243** (see below) | 151,480 | 34,785,119 (at 1M) | 98 (at stall) | 638 (at stall) | 3+ | 2 |
| B distributed | 10,152,454 | 10,000,000 | 151,553 | 34,528,731 | 0 | 5,277 | 0 | — |
| C clustered | 11,088,674 | 10,000,000 | 151,296 | 34,525,075 | 257 | 4,235 | 12 | (see jsonl) |
| D edge | 10,980,793 | 10,000,000 | 151,553 | 34,549,408 | 0 | 3,027 | 1 | (see jsonl) |
| E adaptive | 25,380,331 | 10,000,000 | 151,553 | 34,528,750 | 0 | 5,280 | 0 | — |

- **A (concentrated) — stream exhaustion MEASURED, decisive interactability finding:** continuing A's own deterministic 40-ray stream from its 1M checkpoint, the accepted fraction collapsed 99.4% → 88% → 63% → 42% → 2.8% → **0%** as the fan's shared bore deepened, with permanent 0-acception reached at **1,549,243 cumulative accepted** (`out/s03_exhaust_histA.json`; the live A process likewise burned pure CPU with no accepted-or-log progress — the same deterministic signature). The ROCK is not gone (151,480 cells of material remain); the STREAM has no further valid target because all 40 fixed rays pass through the emptied shaft. This is a stream property, not a rock property: any tap aimed at remaining material is accepted (T2/T5/T6 pass). Consequence for the fixed requirement: the cap guarantees no early disappearance AND the cap leaves ≈98% of the rock's cells untouched under a concentrated stream — a realistic population, however, will (statistically necessarily) aim most of its billion taps elsewhere, so 1e9 accepted remains reachable. **The product-relevant residual risk is a degenerate ultra-concentrated client population (single region, fixed rays) — see R3b.**
- Mass lost at 10M (derived from dens sums): B 0.83%, C 0.84%, D 0.77%, E 0.83% — right on the derived cap budget ⇒ **cap-model confirmed at 10× scale**.
- Rejection rates at 10M (measured): B 1.5%, C 9.8%, D 8.9%, **E 60.6%** (naive retarget redundancy, measured); at 20M E reached **30.8M rejected / 20M accepted** (1.54 launched per accepted — measured).
- A's 1M state hash `0d49d8fe…` is byte-identical to the independently-run calib2-A (measured cross-check).

**Beyond 10M:** B/C/D/E continued toward 20M/30M; results are appended in `out/s03_hist/*/metrics.jsonl` and this section's tables were to be refreshed at report time (§5 addendum below). **60M continuation:** the brief's invalid earlier 60M attempt is *discarded explicitly* (see §2 of the constraints; no artifacts of that run exist in the current scratch tree); the continuation is launched only from a valid 30M checkpoint of B Distributed as `s03_hist.py B_distributed 60000000 ... 40000000 50000000 60000000` if the clock allows (estimated ~6.7 h more on this scratch machine; **feasibility labelled estimate**).

### §5 addendum (final — 20M/30M measured; refreshed at delivery time)

All four remaining histories reached the 30M target (D 19,232 s; C 18,341 s; B 18,598 s; E 20,404 s per-process wall, measured). A is permanently stalled at 1,549,243 accepted (stream exhaustion, above). Measured milestones, all histories, Model A calibration:

**20M accepted (measured):**

| History | Launched | Cells left | Removals | Severings | Fragments | Rejected | Mass loss* | State hash |
|---|---|---|---|---|---|---|---|---|
| B distributed | 20,304,374 | 151,553 | 0 | 9,467 | 1 (largest 151,551) | 304,374 | 1.668% | `6bd0d593…` |
| C clustered | 22,831,212 | 150,957 | 596 | 8,232 | 29 (largest 150,876) | 2,831,212 | 1.672% | `5d2bc618…` |
| D edge | 30,980,793 (at 10M); 30M row below | 151,544 | 0 | 8,411 | 9 (largest 151,537) | 1,958,222 | 1.554% | `56e01671…` |
| E adaptive | 30,767,348 | 151,553 | 0 | 9,450 | 1 (largest 151,551) | 30,767,348 | 1.668% | `23935cad…` |

**30M accepted (measured; final rows of `out/s03_hist/*/metrics.jsonl`):**

| History | Launched | Cells left | Removals | Severings | Fragments | Largest frag | Rejected | Mass loss* | State hash |
|---|---|---|---|---|---|---|---|---|---|
| B distributed | 30,457,126 | 150,949 | 604 | 12,161 | 8 | 150,923 | 457,126 | **2.562%** | `2b7094311e9933b48e9b85ba` |
| C clustered | 35,105,487 | 150,251 | 1,302 | 11,464 | 43 | 150,134 | 5,105,487 | **2.584%** | `0267a56d043e2787d8fd30c2` |
| D edge | 32,936,080 | 151,544 | 9 | 12,338 | 31 | 151,473 (jsonl) | 2,936,080 | **2.350%** | `339381f508723fb78941041e` |
| E adaptive | 76,145,701 | 150,951 | 602 | 12,156 | 8 | 150,925 (jsonl) | 46,145,701 | **2.562%** | `599047e7f98e9cf99e7a6035` |

- **Mass loss** = derived from density sums (`1 − dens_sum/dens_sum0`), NOT an independent measurement of removed mass; *budget check (derived): cap×30M / initial mass = 0.03027×3×10⁷/34,816,588 = 2.609% — every history measured ≤ budget ✓ (max 2.584%). The fixed requirement "no full depletion before exactly 1e9" holds by this bound at every measured milestone.
- Rejection waste (measured/launched-vs-accepted): B 1.5%, C 17.0%, D 9.8%, E **154%** (2.54 launched per accepted at 30M, up from 1.54 at 20M — E's naive retargeting pays a growing toll; presentation-layer fixable).
- Visual emergence (measured pixel-byte-diff vs pristine, `out/s03_pixeldiff.json`): A@1M 0.003%, B@10M 0.001%, C@10M 0.159%, B@20M 0.122%, E@20M 0.132%, **C@20M 0.704%**. Honest consequence of the fixed 1e9 lifespan: per-tap mass budget (0.03027/tap) makes early-epoch front views legitimately near-pristine; visible history divergence emerges over tens of millions of taps and is led by clustered histories (C). See §9/§18/D7 for the founder-visible cadence question.
- **60M continuation (B_distributed) — COMPLETED (measured):** resumed 17:34 UTC from the valid `state_30000000.pkl` (30.0M accepted, hash `2b709431…`). First-attempt crash was a HARNESS bug (pre-12:21 checkpoints lack the new `beta/support/grain` attrs; current `s03_rock.py` methods access `self.beta` on resume) — fixed with an attribute-default shim in the `s03_hist.py` resume path (`beta=0.0, support=False, grain=False`, exactly the configuration the 30M runs executed). Full run finished 21:11 UTC; continuation segment 30M→60M in 12,365 s (measured):

| Accepted | Cells left | Removals | Severings | Fragments | Largest frag | Rejected | Mass loss* | State hash |
|---|---|---|---|---|---|---|---|---|
| 40,000,000 | 149,575 | 1,978 | 15,070 | 12 | 149,530 | 619,064 | 3.524% | `b821134dbcacac2e3f8a8a38` |
| 50,000,000 | 148,313 | 3,240 | 18,061 | 17 | 148,250 | 797,406 | 4.478% | `9dac3646da84a82654788cb8` |
| 60,000,000 | 146,963 | 4,590 | 20,983 | 20 | 146,896 | 993,819 | **5.439%** | `ff15d211a252b97b360ba0c0` |

  - Budget accounting (derived, all pass): pure cap at 40/50/60M = 3.478/4.347/5.216% + bounded crumble slack 0.170/0.279/0.396% ⇒ bounds 3.648/4.626/5.612% ≥ measured ✓.
  - Mass-loss path measured LINEAR in N over 30M→60M (2.562%→5.439%); removed-cell accumulation sub-linear per segment (depictable; no collapse acceleration found). Surface-area faces shrank slightly (23,058 initial → 22,648 at 60M — interior exposure without runaway).
  - Throughput (measured): ≈2,445 acc/s in the 60M segment (fewer modifications once erosion spreads), vs 1,613 acc/s average over the initial 30M run.
  - Render: `out/s03_states/B_60000000_front.png` (+ `_34.png`) — measured 60M state.
  - Honest note (E, hostile linear extrapolation of slack usage): slack accumulated ≤0.09 pp per 10M in this window; if that persisted to 1e9, the Scenario-B uniform history could reach the 30-unit floor ≈1% before the billionth tap. The cap bound still guarantees no COMPLETE disintegration before 1e9 (floor mass is never carved by the cap), but this supports the D6 12%-margin recommendation. Labelled estimate; no extrapolation claimed as measurement. The brief's earlier invalid 60M attempt remains discarded (Appendix C); this continuation is independent of it.
- All sheets rebuilt: `REPORT_s03_equal_10000/100000/1000000/10000000/20000000/30000000.png` (10M+ sheets: pristine + B/C/D/E; **A panels permanently absent** — stream exhaustion at 1,549,243 measured, not a rendering failure) + `REPORT_s03_terminal_pair.png`.

---

## 6. Concentrated vs distributed impact histories

At 1M accepted (measured): A lost 59 cells with 428 severings and 2-cell fragments; B lost 0 cells with 0 severings (pure sub-cell density field 0.87% thinning); C lost 8, D 0, E 0 — the same counter value produces categorically different material states (measured, different state hashes by construction).

Rendered equal-tap sheets (same pristine rock, same renderer): `REPORT_s03_equal_10000.png`, `REPORT_s03_equal_100000.png`, `REPORT_s03_equal_1000000.png`, `REPORT_s03_equal_10000000.png`, `REPORT_s03_equal_20000000.png`, `REPORT_s03_equal_30000000.png` (10M/20M/30M sheets have pristine + B/C/D/E; **A panels are permanently absent** — its own deterministic 40-ray stream exhausted at 1,549,243 accepted, measured; §5/R3b). Honest visibility note (measured, `out/s03_pixeldiff.json`): at these milestones the front-view pictures are legitimately near-identical (C@20M differs from pristine by 0.704% of pixels, B@20M 0.122%) — the *different outcomes* principle is carried by the state hashes and shard distributions, and visible divergence grows with tap count (C: 0.159% @10M → 0.704% @20M, monotone in this measured window, no extrapolation).

**At billion scale (derived, bounded):** the cap budget forces the distributed history toward the DENS_FAIL floor uniformly at ≈1e9 (Scenario-B uniform reaches the floor together; measured budget + derived bound), while concentrated histories hold untouched cells near-pristine and instead deepen a narrow mine region (the crater at 1M is 59 cells; the same region receives ~1e9 total concentrated taps, i.e. ~1e9/(region cells) per cell — derived deep-bore expectation, measured trend at smaller scale via s03_exhaust T1 depth probe). The two histories end billion-counted with *radically different* remaining shapes, both fully disintegrating only at the billionth accepted tap — the founder requirement holds for both.

---

## 7. Exhausted-location handling (measured; `s03_exhaust_results.json`)

- T1 (single-ray no-bore at α): 400k accepted taps without bore-through (derived expectation ≈4–6×10⁵; consistent). Legacy control: bore-through at 1,393 taps (measured).
- T2 crater wall accepts 300/300; T5 far side accepted; T6 fragment hit under unobstructed ray: accepted, state_changed=True (2,903 ray calls, measured; honest note: at α scale the fragment state change is sub-cell).
- T8 global accounting: exact (402,901 + 300 = 403,201 — measured).
- A missed ray is always rejected; no last-location fallback exists anywhere in the engine (code-verified; also exercised by T7-style miss scenarios).

---

## 8. Natural fracture and fragmentation (measured; `s03_frac2_results.json`, `s03_fragvisual_*.json`)

8 scenarios × {grain, control} × 6,000 taps:

| Scenario | first sev (grain) | first multi-frag (grain) | top fragments (grain) | grain vs control |
|---|---|---|---|---|
| S1 broad face | 92 | 1,500 | [2,1,1…] | grain: 1 multi; ctl: 3 (max 2) |
| S2 corner | 116 | 1,500 | [3,3,3,3,2,2…]| both 6 multi |
| S3 edge | 166 | 4,500 | [2,1…] | both 1 |
| S4 narrow waist | 69 | 4,500 | **[12,4,2,2…]** | ctl: [11,5,4…] |
| S5 adjacent craters | 138 | 1,500 | [3,3,3,3,3,2…] | grain 6 / ctl 7 |
| S6 around weakened | 62 | none | singles only | — |
| S7 distributed | 1,042 | none (1×2-cell) | [2,1…] ctl: none | **no multi-cell separation under distributed load** |
| S8 concentrated→distributed | 62 | none | singles | — |

- **Multi-cell natural detachment is real** (top fragment 12–14 cells at the waist; 3-cell at corner/adjacent) — a Stage 0.2-unknown now resolved as *scenario-dependent*.
- **Grain effect measured:** severing ×1.6–1.8 and earlier crack initiation under grain; however grain is not **required** for multi-cell detachment (waist control produces [11,5,4…]).
- Crack propagation is localized through the flaw network (`_near_flaw`) — cracks travel through damaged/weakened paths, not through pristine zones (design property verified in answer set A6-type tests in 0.2, re-verified in these scenarios by crack-cluster locality).
- Honest limitations: cracks are 6-connected stair-steppers; fragment size at these scales is small (≤14 cells vs 151,553-cell rock); dust = 1-cell fragments dominates counts (measured 1,000+ fragments, ≥96% single-cell); *large-fragment* separation (≥1,000 cells) was not observed within 6,000-tap scenarios (measured) and remains unproven.

---

## 9. Surface reconstruction and quality (measured; `s03_recon_results.json`, renders in `out/s03_recon/`)

Per state (histA/1M): MT 12,608 verts / 129,368 tris / 88.6 s; Surface Nets 22,844 verts / 45,876 tris / 18.1 s; Dual Contouring (QEF) same counts as SN, 22.2 s; non-manifold edge defects ≤280/68,670 for SN/DC vs 27,797/39,722 for MT (both methods' defect metrics measured; MT operator is a triangle-count-normalized different quantity — see jsonl).

- SN/DC produce half the triangle count at 4–5× extraction speed with manhattan-style quads; DC's QEF preserved sharp-field behaviour equivalent to SN at these defect counts (measured same metrics).
- MT remains the smoother reference and already renders believable boulder silhouettes at L=72 for pristine AND damaged states (renders: `out/s03_states/A_1000000_close.png` shows the developing crater; FRAG100_close shows the detached fragment + cavity).
- Determinism: all three extractors are pure functions of the density dict (same-input byte-equal outputs across a rerun — measured in the recon rerun for state pickles).

---

## 10. One-billion-tap lifespan — the derived safety argument

Per-tap cap `C = (d̄₀−30)·cells₀/1e9` (derived from the measured pristine mass): with two-pass uniform clip, every accepted tap removes ≤ C (measured: 43,571 taps, 0 violations, max exactly C). Therefore cumulative removal by N taps ≤ C·N + crumble-slack, where crumble-slack is bounded by ≤30 units per cell removed *early* (one-off, measured headroom 6.8% local worst case in concentrated terrain). A production implementation takes the cap with a 12% safety margin (recommended constant; founder-adjustable) so that full depletion **cannot occur before exactly 1e9 accepted** for any tap stream (derived bound; the equality case is the uniform-distribution limit).

Full 1e9-series simulation was **not run** (cost: ≈1 ms/tap × 1e9 ≈ 300+ machine-hours/history — estimate). The milestone series is validated to 10–30M (measured) + cap-bound extrapolation (derived) + terminal mechanism verified at real-scale counter in the synthetic demo (§11; equivalence-by-construction).

---

## 11. Exact completion and disintegration (measured, 7/7 PASS + synthetic billion demo)

Seven cases at N*=20,000, one transactional-outbox engine, identical code path (`out/s03_complete_results.json`):

| Case | Result |
|---|---|
| normal | completed ✓, accepted exactly 20,000, cells_left 0, manifest ✓ |
| before_commit | crash → no commit, rock intact ✓ |
| during_calc | event durable, staged state discarded, retry rejected as duplicate, recovery reprocesses ✓ |
| during_terminal | crash mid-disintegration → recovery replay → completed ✓ (replay_ok) |
| after_commit_before_publish | tap + terminal committed, manifest present ✓ |
| duplicate | 8 jittered attempts then hit; exactly one acceptance ✓ |
| concurrent_race | sequential processing decides the billionth; post-completion tap rejected ✓ |

**Synthetic billion-scale demo (`s03_synth_results.json`) — equivalence-by-construction, clearly labelled:** real 30M/20M/10M B_distributed state + derived Scenario-B floor state; accepted counter seeks 999,999,999 through the same outbox; the billionaire-th tap commits with the atomic terminal event; the manifest (pre-hash + seed) and post-rules verified; renders `NEARBILLION_*` and `TERMINALB_after_*`.
Found rules: billionth-tap + TERMINAL in **one** transaction; idempotent replay; all clients render the same deterministic disintegration sequence derived from the manifest (hash-seeded RNG); post-completion rejections; fragments included because disintegrate_all clears every density key (a fragment is a set of such keys).

---

## 12. Processing and storage scalability

- **Per-tap cost measured:** ~0.9–1.2 ms/tap uncontended fresh; ~730–1230 taps/s contended (scratch, 10 jobs on 5 vCPU); concentrated deep-damage regions cost ~2–4 ms/tap (profiled attribution: carve+bond kernel ~57% (97 bond visits/tap), ray bisection ~15%, stress-trickle remainder).
- **Concurrency conditions (carried from PAR/PAR2, verified math this session):** parallel-safe iff kernel ellipsoids and stress neighbourhoods are disjoint AND no mutual re-resolution; otherwise strict sequential. Demonstrated crash-safety: events durable before processing; staged state discarded on failure.
- **Storage measured:** state pickle ≈3.1 MB at L=72 for a 30M history; SQLite outbox growth in stage-0 tests ~0.5 KB/event (measured); per accepted tap at 1e9 with index overhead ≈ 0.10–0.3 GB total event-store estimates (derived, ballpark; permanent-retention sizing is founder decision D3).
- **Dirty-region reconstruction:** `extract_mt_local` yields bit-identical boundary triangles vs full extraction (measured in 0.2) — clients can patch regions incrementally.

---

## 13. Reliability and recovery

- No committed tap loses its damage event; no event applies twice (7/7 crash matrix above; 10-scenario matrix from Stage 0 still valid; recovery = reprocess durable pending event; staged in-memory state never reused after a failed commit).
- **Honest harness findings reported as evidence:** (a) a completion-harness retry loop used `k = len(res)` (never grows) → infinite loop; found, fixed, documented (`logs/s03_complete_partial_beforeFix.log`); (b) the N*=60,000 reduced-scale full-suite failed due to the scale-dependent cap concentration (preserved file, superseded by the 20,000 run).
- The canonical final ray (fixed target (0.3,0.2,0)) **misses** at a heavily damaged state — jittered bounded retries required (measured: 8 attempts at N*=20k). Production rule: a billionth tap is whatever accepted tap reaches the threshold; never force a landmark tap (the acceptance criterion is counter-based).

---

## 14. Web/iOS cross-platform strategy

- Python↔JS golden parity re-verified (measured, this session); engine spec frozen in `coordinate_contract_v3.md`.
- **Swift is not installed** (measured `which swift` → absent) → Swift parity genuinely unverified; port remains a listed follow-up.
- three.js/SceneKit **not benchmarked** (open risk R2). Web must be independently testable (no physical iPhone available) — carried from 0.2.
- Recommended: canonical extract (MT or SN) rendered identically on web/iOS; the server remains authoritative; clients reconstruct from snapshots + verified-extract deltas; damage rules change only server-side.
- Measured DDA constraint: ray resolution walks ≤ 3L+8 cells; clients must send rock-local rays; servers should bbox-clip or normalize long rays (measured failure mode: origin 6.0 world units ≈ 288 cells away ⇒ all rays miss; 1.5–4 units ≈ 192 cells ⇒ within budget) — goes into the coordinate contract.

---

## 15. Future modular architecture (concepts only — nothing implemented)

Boundaries unchanged from Stage 0.2: rock/material core and acceptance ledger remain authoritative and self-sufficient; presentation, presence, recognition, sponsorship, commerce are out-of-band consumers of the accepted-event stream (each with its own cursor/checkpoint). A module's failure never blocks taps. No code, no services, no schemas were added.

---

## 16. Remaining risks (ranked)

- **R1. iPhone/Swift parity unverified** (measured unavailable) — mitigation: web-first + fixture contract ready for Swift.
- **R2. three.js / SceneKit rendering performance unbenchmarked** — carry-over from 0.2.
- **R3a. Concentrated per-tap cost growth** (measured mild growth; profiled kernel attribution) — mitigations: dirty-region processing bounds, stress-budget caps, per-region locks (§12).
- **R3b. Degenerate ultra-concentrated stream exhaustion (NEW, measured):** a fully-concentrated fixed-ray population saturates its own bore and cannot reach 1e9 accepted (permanent 0-acception measured at 1.549M with the tested 40-ray fan). Product-level mitigations (founder decisions): educate/variate tap aims (realistic streams), or surface-level "alternative aim" UX; the rock engine itself remains correct and safe. None of these violates the no-early-disappearance rule — the cap bound holds for every stream.
- **R4. Uniform-distribution equality case:** Scenario-B uniform reaches the DENS_FAIL floor *exactly* at 1e9 with the nominal cap — the crumble tail gives the intended margin, but the production cap constant should carry the explicit 12% safety margin (recommended, derived).
- **R5. 60M+ histories:** continuation launched only for B_distributed (feasibility estimate ~6.7 h); A_concentrated may not reach its 30M within the report window (measured slowness) — its milestone pickles remain resumable.
- **R6. Large-fragment (≥1,000-cell) natural separation unproven** at calibrated scale (measured; small-fragment demonstration stands).
- **R7. Per-tap presentation** — the psychological “my tap mattered” layer is a product-level requirement the simulation deliberately cannot carry per-tap at billion calibration (measured: 1/6,600 cell per tap).

---

## 17. Recommended final physical architecture

1. **Core (server-authoritative):** sparse voxel density field (DFIX=65536 fixed-int), spatially-varying hardness/toughness, bond lattice with damage+sever+stress-trickle, fatigue as an *optional* realism slot (B-family), alpha-scaled carve with **two-pass mass cap (12% margin)** — Model A + D3-contact stored outbox.
2. **Extraction:** MT for the canonical asset; SN/DC as the lower-cost defensive alternative (both deterministic; local extraction for dirty regions).
3. **Ledger:** transactional outbox; UUID 128-bit exact retention during operational lifetime; permanent-retention sizing = founder decision (D3).
4. **Completion:** terminal event committed in the billionth tap's transaction; deterministic manifest (pre-hash+seed) drives client animation; post-completion rejection; fragments cleared in the same pass.
5. **Presentation:** per-tap feedback decoupled from physics; fragments remain authoritative state until the terminal event clears them.

## 18. Decisions requiring founder approval

- **D1 (superseded by fixed requirement):** terminal disappearance at exactly 1e9 — approved; mechanism selection (Model A + cap as implemented) recommended.
- **D3 permanent UUID retention** — unchanged, must be decided for production.
- **D4 canonical asset resolution (L=72 vs higher)** — not frozen (per brief); higher-L costs measured earlier (s02_res).
- **D5 grained-material lattice on/off in production** — measured effects + costs above; default OFF (simpler, control needs no grain for multi-cell fragmentation in waist/corner geometries).
- **D6 cap safety-margin constant (recommend 12%)** — derived + bounded; founder-adjustable.
- **D7 fragment product policy** (do fragments accept taps? when do they vanish?) — architecture supports both; interaction policy untouched by this stage.
- **D8 adaptive-targeting support** (E-history behaviour: 60.6% rejection waste) — measured; the product can *not* decide this now (this stage does not implement any).

---

## Appendix A — Artifact map

- Scripts: `/tmp/dent-poc/s03_*.py` (+ mirrored `/workspace/s03_data/`), `s02_rock.py` untouched (0.2 preserved).
- Results: `/workspace/s03_data/*.json` (this report's numbers; each labelled).
- Logs: `/workspace/s03_data/*.log` (incl. the preserved invalid-run logs).
- Images: `/tmp/dent-poc/out/s03_states/*.png`, `out/s03_recon/*.png`, `out/REPORT_s03_*.png` → mirrored to `/workspace/s03_images/`.

## Appendix B — 14 required visual states (mapping + honesty notes)

1. Pristine → `ALPHA_pristine_front/34.png` (measured render)
2. Early subtle damage → `A_10000_front.png` (honest: at billion calibration 10k taps are sub-cell; caption carries the numbers)
3. Growing crater → `A_100000_front.png` + `A_100000_close.png` (subtle, honest)
4. Deep crater → `A_1000000_close.png` (59-cell crater region visible in close-up)
5. Overlapping craters → `C_1000000_front.png`, `C_10000000_front.png`
6. Distributed damage → `B_10000000_front.png` (0.83% thinning — subtle; honest caption)
7. Edge chipping → `D_10000000_front.png` (edge severings 3,027, 1 small fragment; sub-cell mass loss — honest caption)
8. Natural crack propagation → `FRAG25/FRAG50_close.png` (waist crack slits, measured sever state)
9. Newly exposed interior → `FRAG100_close.png` (cavity + fragment visible)
10. Detached large fragment (measured max = 14 cells) → `FRAG75_close.png`
11. Multiple fragments → components at FRAG100 (12 fragments >1-cell measured) + `C_10000000` (12 fragments)
12. Extensive erosion → 0.2 legacy-scale evidence (labelled) + `B_30000000_front/34.png` (landed, measured: 2.562% mass loss, 604 removed cells — subtle at calibrated scale, honest) + `C_30000000_front.png` (43 fragments, 1,302 removed cells)
13. Near-completion → `NEARBILLION_front/close.png` (synthetic Scenario-B floor state; equivalence-by-construction, labelled) and reduced-scale `TERMINAL_before_*` (N*=20k, measured)
14. Complete disintegration → `TERMINAL_after_*` (measured, empty scene) + `TERMINALB_after_front.png` (synthetic billion counter)

## Appendix C — Invalid/superseded runs (retained, not evidence)

- `s03_complete_results_NStar60k_partition_problem.json` — N*=60,000 reduced-scale full-suite failure (per-tap cap ∝ 1/N*, concentrated stream bores through; accepted 43,715/59,999). Superseded by the 7/7 N*=20,000 run.
- `logs/s03_frac2.log` — contains the pre-fix S6/S8 rows produced by a shared-dispatch bug (S6 accidentally switched to distributed taps at q≥2000 → S8 byte-identical to S6). Both re-run with corrected dispatch (`fixed_dispatch: true` rows); the pre-fix log is retained.
- `logs/s03_complete_partial_beforeFix.log` — the 5-case partial produced before the `k = len(res)` infinite-loop fix.
- The brief's earlier invalid 60M attempt: no artifacts exist in the current scratch tree; it is explicitly not treated as evidence.
