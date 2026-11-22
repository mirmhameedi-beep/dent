# CONSERVATION_ENGINE_INVESTIGATION.md

**Dent — Conserved Material Ledger + Spatially Local Damage: isolated research / proof-of-concept**

- **Status**: feasibility investigation only. No product code was implemented. The Dent repository,
  evidence branch `vibe/stage03-artifacts-a7e03e`, and PR #10 were **not** modified. All work lives in
  the scratch sandbox at `/tmp/dent-poc/conserved-material/` (read-only worktree of the evidence branch
  at `/tmp/dent-stage03/` used for reference; `s03_rock.py` copied byte-identically, md5
  `0e82227f77fe80dc843a847c7debc8a5` verified against the branch).
- **No billion-tap physical simulation was run.** Terminal behaviour was demonstrated at N\*=5,000 and
  lifetime behaviour at N\*=20,000 taps; the one-billion guarantee is a **derived bound validated at
  compressed scale (measured)**, exactly as in Stage 0.3.
- **Labelling convention**: every conclusion below is labelled **[measured]** (observed in this POC),
  **[derived]** (follows arithmetically from measured inputs), **[estimated]** (extrapolation, no
  simulation), **[hypothesised]** (plausible, untested), or **[unknown]** (cannot be decided here).

---

## 1. Executive verdict

**The required "conservation" property is already implicit in Model A, and the billion-tap guarantee
does not need a new engine to be made exact — the ledger, however, is the cheapest way to make it
*auditable*. [derived, measured]**

1. **The exact guarantee holds and is already encoded in Model A's constants [derived].** Model A's
   per-tap cap `C = (d̄₀ − 30)·cells₀ / 1e9` is *algebraically identical* to the conserved-ledger
   quantity `q = (M₀ − M_r)/N` with `M_r = DENS_FAIL·cells₀`:
   evidence branch: `(34,816,588 − 30·151,553)/1e9 = 30,269,998/1e9 = 0.030269998` legacy units/tap —
   bit-exact match to `s03_calib2_results.json` cap `0.030269998`.
   The POC reconstruction: `(33,977,655 − 30·147,908)/1e9 = 0.029540415` — the exact cap used in E6.
   Model A + a fixed-point integer residue ledger therefore gives the full guaranteed accounting at
   **~+9 % per-tap cost [measured]**, without fragile/debris/hierarchy machinery.

2. **The conserved ledger (Option B) works. [measured]** In E1–E4 over 87,887 accepted taps across 8
   histories and 2 debris policies, the integer identity
   `M₀ ≡ density(main+fragments) + debris + fines + consumed + burned` held with residual **0** at
   every milestone, the per-tap allowance was never exceeded, and `physical(n) > M_r` held after
   *every* accepted tap, including hostile streams. Zero violations of any kind.

3. **Option C (hierarchical spatial resolution) is a negative result at this scale. [measured]** The
   6-cell hierarchical DDA reached exact contact-cell parity (0/600 mismatches) but ran at
   **0.79× the speed** of the flat DDA in CPython (only 74/965 blocks were empty at L=72). It does
   reduce ray work when fill fraction is low [hypothesised], which favours deferring it.

4. **A serious, engine-family surface defect was found on the *existing* Model A ray code [measured].**
   On damaged states, **82.1 % of accepted hits** land where trilinear density is **below
   DENS_ISO = 120** (median 73.9); only **27.7 %** of accepted hits lie within 0.15 cells of the
   independent first iso-crossing (worst error **26.3 cells**). The DDA's contact criterion is
   `density > 0` while the visual surface is the ISO isosurface, so low-density "fluff" (30–120 band)
   in front of true crater walls is hit first. **This is a defect in the current Stage 0.3
   implementation that must be fixed regardless of which architecture is chosen** — it is a direct
   threat to requirement 2 ("a tap must hit the actual current visible surface") and to requirement 7
   ("collision/damage must use the same canonical surface as display").

5. **Recommendation [derived from measured evidence]: adopt "Model A + integer ledger + ISO-consistent
   ray contact" (a minimal Option A'), not the full Option B/C architecture.** The conserved ledger is
   worth keeping as a thin, opt-in audit layer and as the migration path; hierarchical resolution and
   debris aggregation should be prototypes again later, when fragment/debris *policy* is a product
   decision. Fragment accounting as simulated produces enormous numbers of 1-cell fragments (33,015
   components over 36,815 fragment cells = 1.1 cells/component [measured]) — an unmanaged
   implementation detail, not a feature. Full Option B/C machinery is currently
   unjustified complexity for a solo founder.

The concept was challenged as instructed (§10); several of its premises were *weakened* by the
evidence, and this report does not rubber-stamp the original proposal.

---

## 2. Explanation of the proposed architecture

The proposed architecture (the founder's brief, §2 of that brief) contains two independent principles:

**A. Spatially local damage.** Each accepted tap affects only material near its actual impact point;
the physical outcome must be a function of the local impact history. This is *already* how Model A
works: `s03_rock.py` carves only cells within the impact radius of the hit location; nothing global
exists except the (necessarily global) counter and cap. Requirement 8 in the POC is satisfied by
Model A's own structure [measured; see §7 E4].

**B. Globally conserved material accounting.** The engine maintains an authoritative integer
inventory

```
M₀  ≡  Σ density(main field + fragment cells)  +  Σ debris[block]  +  Σ fines[block]
       +  consumed  +  burned           (all in fixed-point integers, exact)
```

with four material classes exactly as the brief asks: main rock, detached fragments, persistent
aggregated debris/dust, and irreversibly consumed material. Density-threshold ("crumble") cell
deletion must route the cell's *entire residual* into one of these classes — never drop it. A cell
becoming non-viable is a *representation change*, not a destruction event.

The proof-of-concept implementation `cm_rock.py` realises this as a subclass of Model A's
`RockDensity` (`ConservedRock(A.RockDensity)`), so that main-rock erosion is **form-identical** to
Model A (same alpha-scaled two-pass capped carve) and the comparison in §9 is apples-to-apples:

| POC component | Role |
|---|---|
| `modelA_stage03.py` | byte-identical copy of `stage-0.3/scripts/s03_rock.py` (baseline) |
| `common.py`, `s01_c.py` | shared helpers; **stub voxelizer** (see §6, missing-file note) |
| `cm_rock.py` | `ConservedRock`: integer ledger, κ-split routing, crumble-residual transfer, per-tap vs cumulative allowance, hierarchical DDA, terminal event with guards |
| `streams.py` | deterministic impact streams (histories + hostile) |
| `exp1..exp7*.py` | the seven required experiments |

Engine parameters (all POC): lattice L=72, `dfix=65536` fixed point, `DENS_FAIL=30`, `DENS_ISO=120`
(both inherited from Model A), debris macro-block `BLOCK=6` cells (12³ blocks), hierarchical-ray block
`HB=6`, κ = 0.5 ([chosen for symmetry](#) — a product constant, not a physical constant).

**Honest implementation-order difference to disclose [measured by code inspection]:** `ConservedRock`
pops crumbled cells inside `_apply_carves` (before Model A's bond pass), whereas Model A pops them
after the bond pass. Conservation arithmetic is unaffected (both paths route the full residual into the
ledger); severance *counts* can differ slightly from Model A at identical taps. This is a POC
structural difference, not a physics difference, and must be resolved if the ledger is grafted onto
Model A.

---

## 3. Mathematical derivation of the one-billion-tap invariant

Let (all integers, fixed-point dfix units = legacy units × 65,536):

- `M₀` = initial inventory (measured: 2,226,759,598,080 dfix = 33,977,655 legacy for the POC rock;
  evidence-branch rock: 34,816,588 legacy).
- `M_r` = minimum reserve that must remain for `n < N`. The physically honest floor is the mass of all
  cells that would crumble: `M_r ≥ DENS_FAIL · cells₀` (every cell reduced to its floor is whole-cell
  removal territory). POC: `M_r = 30 · 147,908 = 4,437,240` legacy = 13.06 % of M₀ [measured calib].
- `N = 1,000,000,000`.
- `q = ⌊(M₀ − M_r)/N⌋` = maximum *irreversibly consumed* material per accepted tap.

**Invariant to prove:** for every accepted-tap count `n < N`,
`physical(n) ≡ main + fragments + debris + fines ≥ M₀ − n·q`, hence `physical(n) > M_r`;
and at `n = N` the terminal event may remove everything (`burned ← M₀ − consumed`).

**Every consumption route, audited (the brief's checklist, §3 of the brief):**

| # | Code path | Where material goes | Can it exceed allowance? |
|---|---|---|---|
| 1 | Clipped carve take on a cell that stays alive (`take·f` below the ≥0 ceiling) | the removed part is routed: `κ` → `consumed` (≤ per-tap budget), `1−κ` → `debris[block]` | No — `consumed` increments are budget-clamped inside `_consume_or_debris`; the rest is *transfer*, not consumption |
| 2 | Clipped residual beyond a cell's floor during carve | capped by `M_r` construction; residual > allowance overflows into `debris` (transfer), only `κ`-part into `consumed` within budget | No |
| 3 | Crumble (cell drops below `DENS_FAIL`): **whole cell** leaves the field | full residual `dcur` routed via the same budget-clamped split → `consumed ∪ debris` | Consumption part clamped; the crumble *slack* (≤ `DENS_FAIL` per cell, one-off per cell) is soaked by `M_r ≥ DENS_FAIL·cells₀` |
| 4 | Fixed-point rounding (`int(round(newd))`) | the exact applied integer delta `dcur − newd_int` **is itself** the routed residual — round-off cannot escape by construction | No [derived; measured residual 0] |
| 5 | Fragment separation (a component disconnects) | cells stay in the density field with unchanged values; the ledger classifies them at milestones only — mass unchanged, class changes | No mass motion at all |
| 6 | Debris shed / fines (policy experiment) | debris → fines + ⊂budget consumed, inside `_check_invariant` per tap | No |
| 7 | Terminal event | `burned ← M₀ − consumed`, all physical structures cleared; guarded, idempotent | Authorised exactly once at `n = N` |
| 8 | Cleanup / unset paths | **none exist** — the POC has no code that removes mass without routing [measured by inspection + 0 residual] | — |

**Why the bound cannot be broken [derived + measured]:**
`consumed(t) ≤ t·q` is checked after *every* accepted tap (`_check_invariant`, cm_rock.py:194). Because
`consumed` is the *only* decrement of physical material (all other routes are transfers), and every
consumption increment is clamped to the remaining per-tap budget, `consumed(t) ≤ t·q` holds for any
stream. Therefore `physical(t) = M₀ − consumed(t) − burned(t) ≥ M₀ − t·q > M_r` for all `t < N`.
Critically, this is a property of the *conservation rule*, not of the impact distribution — E3
confirmed it under concentrated, rotated-fan, distributed, clustered, edge-focused, adaptive and
hostile streams with zero violations [measured].

**Per-tap vs cumulative allowance [measured, E3]:** the cumulative mode
(allowance `= M₀ − M_r − consumed`, "spend anything still unspent") produced **byte-identical audit
results** to per-tap mode, because the mandatory two-pass carve clip (`f = min(1, cap/total)`) already
bounds each tap's total take to `cap`, so unspent allowance can never accumulate into a "sudden huge
impact later". Per-tap is nevertheless recommended for production: it is *locally* enforceable (an
attacker/replay cannot amortise) and needs no global counter read in the inner loop. The brief's worry
about unused allowances is thereby answered for this design [measured under the tested regimes;
[unknown] for exotic pathological histories beyond the 8 tested].

**The two questions are separate [derived]:** the survival guarantee says *if* `n` accepted taps
happen, material persists for `n < N`. Whether any specific ray sequence can *generate* 1e9 accepted
taps is a different (stream/geometric) question. Model A's R3b finding (a concentrated fixed 40-ray
fan exhausts its bore; rock fully intact) reproduces here: at compressed scale `A_concentrated`
stalled at **38 accepted / 800,000 launched** [measured, same signature]. The engine never redirects
misses (E5/T2); the product must handle degenerate ultra-concentrated populations at the UX level, as
Stage 0.3 already recommended.

**Scale cross-check [derived]:** at true billion scale, `q_POC = 0.029540415` legacy/tap removes
86.94 % of M₀ by the billionth tap; mean cell density 229.72 ⇒ one cell-equivalent removed per
**~7,776 taps** (POC) / **~7,590 taps** (evidence-branch cap 0.03027) [derived]. Both numbers are
derived, not measured; no 1e9-run exists in either Stage 0.3 or this POC.

---

## 4. Exact definitions of material consumption and transfer

Integer dfix units throughout (`1 legacy unit = 65,536 dfix`). Rounding is `int(round(·))` and the
round-off is *included in the applied integer delta*, so rounding never loses mass [derived; measured
residual 0 in every audit].

- **Main field**: sparse dict `cell -> dfixedensity`.live cell ⇔ present in dict.
- **Fragment**: any connected component (6-neighbour, computed at milestones only, O(V) ≈ 280 ms
  [measured]) of the main field other than the largest. Fragments are ordinary density cells —
  hittable through empty space (E5/T4, 36/36 [measured]).
- **Debris[block]**: 6³-cell macro-block aggregated mass (single integer per block, ≤ 1,728 blocks).
  Transfer representation; hittability of debris cells is intentionally *not* implemented in the POC
  (policy open — §12).
- **Fines[block]**: dust subclass of debris under the shed policy (visual-class distinction only).
- **Consumed**: irreversibly removed. Only two writers: budget-clamped κ-split of residuals, and the
  shed policy's budget-clamped take.
- **Burned**: terminal-event destination; single guarded, idempotent transfer.

**The invariant checked per tap** (`_check_invariant`, cm_rock.py:186–199):
`main + (debris + fines) ≡ M₀ − consumed − burned` **and** `consumed ≤ n·q + burned` **and**
(`n < N` ⇒ `physical > M_r`). `audit_ledger` recomputes everything O(V) from the field (no trackers
trusted) — full-recount drift was **0** at every milestone in E1–E7 [measured].

**Honesty clause [measured by inspection]:** debris/fines are *not* renderable geometry in the POC —
they are honest mass in the ledger but invisible. The brief explicitly forbids using invisible
accounting "to pretend material is present": this is flagged as an **unresolved representation debt**
in §10/§12; under the recommended architecture (below) debris mass is bounded so the debt is small.

---

## 5. Comparison of Options A, B, C

**(A) Existing sparse-voxel density model + improved accounting.** (B) Sparse voxels + conserved
fragments/debris (= what `ConservedRock` implements). (C) Hierarchical representation (sparse voxels +
coarse blocks + aggregated fragments + inventory + local geometry reconstruction; POC tested the
hierarchical-DDA component only).

| Axis | A (existing) | B (conserved) | C (hierarchical) |
|---|---|---|---|
| Physical realism | crater/fragment physics already present [measured] | identical field physics + routed residuals [measured] | must preserve parity with A (POC DDA did, 0/600 mismatches [measured]); block-boundary artefacts untested [unknown] |
| Mathematical reliability | cap gives the bound but residue is only *implicitly* bounded (6.8 % crumble tail measured in Stage 0.3 V3) [derived] | **exact integer identity, residual 0 everywhere [measured]** | inherits B's ledger if included; adds block-boundary conservation cases [unknown] |
| Spatial accuracy | ray defect (82 % sub-ISO hits [measured]) — fix in any option | same defect (same ray code) [measured] | same, plus possible block-seam discontinuities [unknown] |
| Fragment behaviour | fragments exist in the field implicitly; death = unaccounted mass loss [measured] | fragments classified + mass-respecting; 1.1 cells/fragment explosion needs policy [measured] | unknown beyond POC |
| Surface-hit accuracy | same defect as above | same | same + seam risk [unknown] |
| Memory | ~60–90 MB RSS [measured] | identical (+ ledger integers, debris 2–837 blocks) [measured] | unknown; block index adds ~O(blocks); expected lower only when mostly-untouched [hypothesised — POC had 92 % occupancy] |
| Processing cost/tap | 0.35 / 0.50 ms (conc./dist.) [measured] | 0.379 / 0.544 ms (**+8.3 % / +8.6 %**) [measured] | unknown; hier DDA alone was *slower* (0.79×) in CPython [measured] |
| Rendering complexity | single path (marching-cubes style iso field) | + debris rendering decision [open] | + coarser blocks + seam stitching [estimated significant] |
| Implementation complexity | baseline (+ small ledger patch) | moderate: 1 new class (~350 LOC) on top of A | largest: 4 representations + reconstruction + parity proofs |
| Solo-founder maintainability | **best** — one field, one code path, auditable cap | good — ledger is separable and testable (all 7 experiments are scripted) | **worst** — this POC's negative speed result gives no offsetting benefit |

---

## 6. Experimental methodology

- **Environment**: scratch container, pure-stdlib Python 3.12, git worktree of the evidence branch
  (read-only reference). Timings are scratch-machine numbers, not Railway/device capacities.
- **Initial rock parity**: the original voxelizer `s01_c.py` is **not present on the evidence branch**
  (missing from `stage-0.3/`); a stub inside-test voxelizer against `common.rock_surface` was written.
  Reconstructed POC state: **147,908 cells / 33,977,655 legacy units** vs evidence **151,553 / 34,816,588**
  (−2.44 % cells); mean density 229.72 vs 229.73 ⇒ *same material*, slightly different boundary
  [measured]. All cross-engine comparisons in this POC use the POC state on both sides, so results are
  internally fair; absolute comparisons against the evidence branch carry this 2.4 % offset [measured].
- **Calibration regimes** (both used, deliberately):
  1. *Billion-α regime* — α = 0.00197456 (Stage 0.3's billion calibration), N\* = 20,000 with a
     proportionally loosened allowance (q_tap = 1,477.02 legacy/tap). Tests accounting correctness at
     Model-A-like erosion rates (E1, E5, E6, E7 directional).
  2. *Compressed-lifetime regime* — α inflated (q_legacy/15.33) so that a 20,000-tap run depletes the
     rock toward its reserve, i.e. allowance actually binds (E2, E3/E4, E5-damage, E7). This is where
     the invariant gets stress-tested.
- **Independent ray checker** (for E5): fine-step traversal (0.25-cell sampling + 30-step bisection)
  of the *same trilinear field*, first `t` with `density ≥ DENS_ISO`. Hit is correct iff verdict
  matches and `|t_engine − t_ind| ≤ 0.15` cells. A checker bug found during E5b (projection used the
  same component in all 3 axes) was **fixed and confirmed to be a checker bug only** — engine results
  did not change.
- **Streams** (`streams.py`): deterministic, seeded; A_concentrated (fixed 40-ray fan), A_rot (re-aims
  the fan every 20 accepts), B_distributed, C_clustered, D_edge, E_adaptive, and a hostile stream that
  bores a single target until recent acceptance < 50 % over 500 launches, then pivots.
- Reproducible commands: §13.

---

## 7. Measured results

### E1 — Material conservation (billion-α, 20k taps × 3 histories, hold policy)

At milestones 1k/5k/10k/20k, in A_concentrated / C_clustered / B_distributed:
`balance_residual = 0`, `tracker_drift = 0`, ledger/allowance/reserve violations **0** everywhere
[measured]. Aggregate routed mass at 20k: consumed 354.5 + debris 360.2 legacy units in A_concentrated
(≈ 23,233,620 + 23,606,974 dfix — exact identity with the field loss 46,840,594 dfix). No fragments at
this scale. Debris concentrated in very few blocks under concentrated impact (2 blocks) and spread
when distributed (323–408 blocks) [measured]. Full data: `results/e1_conservation.json`.

### E2 — Threshold handling (compressed, distributed, 20k taps, both policies)

**104,495 cells driven below the DENS_FAIL threshold**; every crumble residual routed; final identity
exactly `M₀` in both policies; 0 violations [measured].

| Policy | main (frac of M₀) | debris blocks | fines | consumed | exterior fragments |
|---|---|---|---|---|---|
| hold | 26.42 % | 36.82 % of M₀ in 837 blocks | 0 | 36.79 % | 32,936 comps / 37,870 cells, largest 5,543 |
| shed | 26.42 % | 9.28 % (3,153,300) | 13.76 % (4,674,324) in 688 blocks | 50.54 % | same |

(All units legacy; 6,409 shed events under shed.) The κ = 0.5 split means *half* of all routed
residual is irreversibly consumed even under `hold` — an important tuning observation: κ is the
product knob controlling how much "eroded" material stays *visibly present* (debris) vs vanishes
(consumed). Full data: `results/e2_threshold.json`.

### E3 — One-billion lifetime invariant (compressed, 7 streams + cumulative mode)

Invariant `physical(n) > M_r`, ledger identity, and allowance checked **after every accepted tap**:
**0 violations in all 8 runs** (87,887 accepted taps total) [measured]. Pre-terminal main-rock
fractions of M₀ — the same compressed lifetime, radically different physical states:

| Stream | accepted / launched | main frac | debris+consumed frac | largest fragment |
|---|---|---|---|---|
| A_concentrated (fixed fan) | 38 / 800,000 (bore exhausted — mirrors Model A R3b) | 99.84 % | 0.16 % | whole rock |
| A_rot (re-aiming fan) | 20,000 / 31,509 | 26.25 % | 73.75 % | 6,761 |
| B_distributed | 20,000 / 30,999 | 26.42 % | 73.58 % | 5,543 |
| C_clustered | 16,573 / 800,000 (grid region exhausted) | 44.49 % | 55.51 % | 20,870 |
| D_edge | 20,000 / 131,885 | 30.34 % | 69.66 % | 16,599 |
| E_adaptive | 20,000 / 76,753 | 26.27 % | 73.73 % | 7,629 |
| HOSTILE | 15,376 / 800,000 (pivot targets exhausted) | 49.58 % | 50.42 % | 26,251 |
| A_concentrated cumulative-mode | 38 / 800,000 — byte-identical outcome to per-tap | | | |

Stream exhaustion under concentration is a *stream* property (rock intact), consistent with Stage 0.3
R3b [measured]. Full data: `results/e3_e4_invariant.json`.

### E4 — Spatial differentiation

Requirement 4/5/6 satisfied **[measured]**: equal accepted-tap counts produce clearly different states
(see E3 table: main fractions 26.3 %–49.6 %, largest fragments 5.5k–26k cells; debris spread 2–837
blocks in E1/E2). Differentiation is *emergent from spatial history*, not coded per-history.

### E5 — Surface interaction (and the Stage-0.3 ray review, §7 of the brief)

- **T1 pristine accuracy (Model A copy, unchanged)**: 300 outside rays, 92 % within 0.15 cells of
  independent first-ISO crossing, max error 3.96 cells [measured] — good on pristine geometry.
- **T2 empty bores**: 39/50 repeated bore rays correctly rejected; rejected rays left state
  byte-unchanged in 39/39 rejects; no redirection [measured]. *(Harness weakness, disclosed: the
  logged `hash_unchanged_after_burst` check is trivially true due to an `or True`; the per-reject
  dict-comparison is the load-bearing check [measured].)*
- **T3 damaged rock**: conserved engine 1,422 accepted/1,500, verdict agreement with independent
  checker 95.1 %, but only **25.0 % of accepted hits** within 0.15 cells (max err 26.3 cells);
  **Model A: 23.8 %, max err 22.9 cells, 97.9 % verdict agreement** [measured]. **The defect is
  engine-family, not conserved-specific.**
- **Deep quantification (E5b, 1,423 accepted rays)**: **82.08 % of accepted hits land at trilerp
  density < DENS_ISO = 120** (1st pct 10.4, median 73.9, 90th pct 120.0); only **27.69 %** within
  0.15 cells of the first ISO crossing; error median 0.458, p90 2.28, worst 26.3 cells [measured].
  Root cause [measured by inspection + experiment]: the DDA contact criterion is
  `density > 0`, the visual surface is `density ≥ DENS_ISO = 120` ⇒ sub-ISO "fluff" (30–120 band) in
  front of true crater walls is contacted first; when an entire contact cell is sub-ISO, bisection
  converges to its interior centre, returning an off-surface point. Consequence: taps deposit damage
  up to **26 cells deep** relative to the visually rendered surface — a direct threat to requirements
  2, 5, and to the collision/display canonical-surface rule (§5 of the brief).
- **E5c verdict split (corrected final measurement, 120 rays per kind)**: accept/reject verdicts agree
  with the independent checker for axis **120/120**, grazing **119/120** (1 engine-hit/ind-miss),
  oblique **118/120** (2 engine-miss/ind-hits); max positioned error 19.5 cells (axis), > 5-cell
  errors 1/3/1 [measured]. Resolution (accept-vs-reject) is essentially correct; *positioning* on
  damaged rock is the real defect. Data: `results/e5c_grazing_split.json` (supersedes the degraded
  T5 numbers in `e5_surface.json`).
- **T4 fragments**: 36/36 rays through empty space accepted on fragment cells of exposed fragments
  [measured] — newly exposed interiors are genuinely hittable (requirements 6, 9 for interior
  surfaces); measured at compressed scale only.

### E6 — Efficiency (billion-α, 5,000 taps, cap enabled, full parity cars)

| Metric (per-stream) | Model A | Conserved | Delta |
|---|---|---|---|
| ms/tap, A_concentrated | 0.350 (ray 0.069) | 0.379 (ray 0.071) | **+8.3 %** |
| ms/tap, B_distributed | 0.501 (ray 0.076) | 0.544 (ray 0.074) | **+8.6 %** |
| modified cells/tap | 33.7 / 33.1 | 33.9 / 33.2 | parity |
| RSS MB | 60.4 / 89.9 | 61.0 / 89.9 | parity |
| full O(V) ledger audit | — | 284–293 ms (milestone-only, negligible amortised) | opt-in |

**Hierarchical DDA (Option C component)**: 600 rays × parity — **0 contact-cell mismatches** vs flat
DDA, but 0.0692 → 0.0879 ms/ray = **0.79× speedup (a slowdown)**; only 74/965 blocks were empty at
L=72 [measured]. In CPython at this occupancy, block-jumping overhead exceeds its benefit. Data:
`results/e6_efficiency.json`.

### E7 — Terminal event (N\* = 5,000, compressed demo — **not** a 1e9 physical run)

- Attempting terminal at N−1: refused (`accepted_counter_mismatch`) [measured].
- At exactly N: single committed manifest (`pre_hash`, `physical_before = 1,624,552,574,144` dfix,
  `burned` = same, `reserve` present, `post_audit_ok: true`, post-state hash =
  `e3b0c442…` — the hash of an empty state) [measured].
- Identity after: `burned + consumed = M₀` exactly; density/debris/fines/severed all empty [measured].
- Idempotent: replay returns the same manifest, `burned` unchanged; post-terminal taps rejected [measured].

---

## 8. Material-conservation accounting (summary of every route, measured)

| Route | Measured handling (E1–E7) |
|---|---|
| carve take (cell survives) | exact integer delta `dcur − round(dcur − take·f·dfix)` routed (κ → consumed within budget; 1−κ → debris) — residual 0 [measured] |
| crumble (cell dies) | whole-cell residual routed identically; 104,495 crumbles in E2, all accounted [measured] |
| fixed-point rounding | included in applied delta; cannot leak [derived + measured residual 0] |
| fragment separation | mass-static reclassification, milestone-only |
| debris shed (policy) | budget-clamped, per-tap checked [measured E2] |
| terminal burn | guarded, single, idempotent [measured E7] |
| any other code path | none exists in POC — verified by full O(V) recount agreeing with trackers at every milestone (drift 0) [measured] |

**Guarantee status: the invariant `physical(n) > M_r` for `n < N` is [derived] from integer exactness
and [measured] to hold per-tap in 8 histories × 2 allowance modes; the equality case at n = N is
[measured] at N\* = 5,000 only, and [hypothesised] to transfer to N = 1e9 unchanged because the
ledger arithmetic is scale-free (only q changes).**

---

## 9. Performance and memory comparison

- **Per-tap cost**: conserved ledger adds **+8–9 %** over Model A at parity (0.35→0.379, 0.50→0.544 ms)
  [measured]. This is the price of exact routing; it is *not* "more expensive than the cap method by
  much" (§10 question answered), but it is not free either.
- **Memory**: identical RSS at 5k taps (60–90 MB depending on stream) [measured]; ledger adds a
  handful of integers and ≤ 837 debris blocks [measured].
- **Full ledger audit**: O(V) recount ≈ 285 ms — fine at milestones only [measured].
- **Hierarchical DDA**: correct (0/600 mismatches) but 0.79× speed [measured] — **no gain in CPython at
  L=72 with 92 % occupancy**; would only pay off when the rock is mostly empty, i.e. near end-of-life
  [hypothesised].
- **No geometry-reconstruction cost is measured here** — Model A serves the field directly;
  block-level meshing was out of POC scope [unknown] — see §12 open decision.

---

## 10. Failure cases and limitations (the challenge section — as requested, not a confirmation)

Measured and reasoned answers to every §10 challenge in the brief:

1. **Does conserved debris create excessive numbers of objects? Yes — if unmanaged. [measured]**
   Fragment *components* explode: 32,936–90,407 components, averaging **1.1 cells per fragment** in
   compressed-lifetime runs (E3). The κ-split *routed* mass is honestly tracked, but as currently
   implemented fragments are just isolated field cells, not meaningful physical pieces; per-fragment
   objects would be unusable in production. Aggregated 6³-block debris keeps it to ≤ 837 blocks
   [measured], which is tractable — **but debris is currently invisible mass (see #5)**.

2. **Is material accounting more expensive than the current cap approach? Marginally (+8–9 %/tap
   [measured]), and worth it only if auditability is a product requirement.** For pure survival the
   cap alone already suffices [derived]; the ledger's value is *auditability and exactness*
   (`balance_residual = 0`), which raw Model A does not offer (Stage 0.3 V3 measured 1.3e-4 relative
   mass drift only via fixed-point round-off, plus a 6.8 % local crumble tail) [measured in Stage 0.3].

3. **Could the rock retain too much mass and look insufficiently damaged? Partly yes at compressed
   scale — a real product risk. [measured]** Main rock retains 26–50 % of M₀ at lifetime end under
   compressed α (E3), i.e. the rock must lose 87 % of its mass *by design* only at the very end; at
   billion-α rates, 20k taps remove ~0.002 % of M₀. Viability depends entirely on presentation-layer
   drama per tap (as Stage 0.3 V7 already concluded). Nothing in the conserved approach makes this
   *worse*, but it does not solve it either.

4. **Is localised damage convincing at a one-billion-tap lifespan? Unchanged from Stage 0.3
   [derived].** q = 0.02954 legacy/tap = 1.29e-4 cell-equivalents = one cell per ~7,776 taps
   [derived]. No POC result changes this; the conserved ledger neither improves nor worsens perceived
   per-tap drama. This remains the product's central presentation problem [unknown, beyond POC scope].

5. **Can aggregated debris be represented honestly? Not yet in this POC — key open gap [measured].**
   Debris is a number per block. Making it visible without inventing fake geometry (e.g., rendering a
   rubble decal or a coarse point cloud per block) is a founder/product decision; the ledger is
   consistent with "what visitors can see" only once that representation is chosen. Risk: honest-but-
   invisible mass, which the brief explicitly rules out long-term.

6. **Does adaptive/hierarchical resolution cause visible or physical discontinuities? Unknown —
   untested at the seam level. [measured only that contact geometry matches exactly at 0/600]:
   the DDA parity test covers ray contact, not mesh seams, not bond physics across block boundaries,
   not rendering. The negative speed result (0.79×) makes this moot at L=72 for now [measured].

7. **Do material-conservation rules make fragment separation less realistic? Possibly, unmeasured
   [unknown].** κ-split routing keeps half the residual *in* debris near the impact, which may
   visually glue fragments to craters unless debris interacts (E2 shed policy sketches one mechanism:
   impacts re-suspend debris, 6,409 events at compressed scale). Large-fragment separation
   **emergent-and-convincing** was **not demonstrated** and is not claimed: largest observed
   "fragment" behaviour = still-connected single components up to 26,251 cells [measured], which the
   connectivity classifier counts, but no *dynamic* fracture animation exists.

8. **Is this approach unnecessarily complicated? The full B/C version: yes, at current scale
   [derived].** The measured negative result on hierarchical DDA, the 1.1-cells-per-fragment
   proliferation, and the equivalence `Model A cap ≡ conserved q` (§3) together show that a thin
   integer ledger atop Model A captures the concept's entire mathematical benefit at ~9 % cost, with
   none of the representation machinery.

9. **Additional defects found (must be fixed in any architecture) [measured]:**
   - the **sub-ISO ray-hit defect** (82 % of accepted hits below visual ISO; 25 %/23.8 % position
     agreement; up to 26-cell depth error) — engine-family, Model A included;
   - the **missing `s01_c.py`** on the evidence branch breaks full reproduction of the initial state
     (POC stub reconstructs −2.4 % cells);
   - `A_concentrated`-style fixed-fan streams self-exhaust (38 accepts) — same R3b family, product
     must meter aim diversity;
   - POC-specific, disclosed: crumble-before-bond-pass ordering difference vs Model A (§2);
     E2 `hash_unchanged_after_burst` check is vacuous (`or True`).

10. **Simpler alternatives, wherever one exists [derived]:**
    - Survival + accounting: **Model A + per-tap floor `q` and an integer residue ledger** (≈ +9 %/tap)
      — recommended.
    - Ray correctness: change contact criterion to `density ≥ DENS_ISO` with ISO-crossing bisection in
      `resolve_ray` (~20 lines, parity-checked against the independent traverser already built).
    - Terminal: the E7 guard structure as-is (already spoof-proof: counter + hashes + idempotency).
    - say no to: per-fragment objects, hierarchical blocks (at L=72), per-particle debris simulation,
      any microservice/distribution — none tested here justified themselves.

---

## 11. Recommended architecture

**"Model A′" — Stage 0.3 sparse-voxel density engine, plus three thin layers. [derived from measured
evidence; the full Option B/C is *deferred*, not rejected forever]**

1. **Keep Model A's physics core** (alpha damage, two-pass capped carve, DFIX fixed point, DENS_FAIL
   crumble) — its cap constant is *already* the conserved q (§3 algebraic equivalence, exact to the
   last digit vs `s03_calib2_results.json`).
2. **Add a conserved integer ledger** (the `ConservedRock` routing of this POC, minus the
   subclassing hack): per-tap allowance `q` (per-tap mode), κ-split of residuals into
   consumed/debris[block], per-tap invariant check, O(V) audit at milestones; terminal event exactly
   as E7. Cost ≈ +9 %/tap [measured].
3. **Fix the ray contact criterion** to `density ≥ DENS_ISO` with bisection to the ISO crossing, and
   make the renderer consume the *same* iso definition. Re-run the E5/E5b/E5c harnesses (already
   built) as acceptance tests until hit-position agreement > 99 % [target; currently 25–28 %
   measured].
4. **Defer**: hierarchical blocks (measured 0.79× at this scale), shed/fines policy, fragment
   interaction games, per-fragment simulation — revisit once the ledger + ISO-ray are stable and a
   real renderer exists; the E2/E5 harnesses are already the right testbed.

Rationale vs the conserved-heavy Option B/C: it achieves requirements 1–12 with the smallest surface
[derived]; every guarantee B offers beyond A′ (exact per-tap audit trail, honest crumble residuals) is
already delivered by layer 2 [measured]; option C's only measured benefit at current scale is
negative [measured].

---

## 12. Outstanding technical and product decisions

| # | Question | Options | Status |
|---|---|---|---|
| 1 | Debris visibility representation | invisible ledger only / block rubble decal / coarse point cloud / rigid mini-bodies | open; POC = ledger-only, honest mass [measured gap] |
| 2 | κ (consumed vs debris split) | 0.5 measured; product likely wants <0.5 (more visible mass) | open product |
| 3 | Debris interaction (shed/hold variants) | hold (inert) vs shed (re-suspends) | open; both tested for conservation [measured] |
| 4 | Per-fragment physics | none in POC; costly [hypothesised] | open |
| 5 | Fragment-size floor and merge policy | open | open |
| 6 | Whether contact surface for collision = rendered ISO exactly | current defect says yes eventually | decisive, engineering |
| 7 | Recover missing `s01_c.py` on evidence branch | re-add from history or regenerate | needed for full reproduction [measured gap] |
| 8 | Milestone-only vs continuous fragment classification | POC = milestones only (O(V) ≈ 285 ms) | open |
| 9 | JS/Three.js + Swift/SceneKit determinism port of (a) DFIX integer ops, (b) float ops in carve kernel | int64 for ledger is portable [derived]; carve kernel uses 64-bit float — **JS double matches Python float bit-for-bit for IEEE-754 ops [hypothesised, untested here]**; Swift likewise, but denormals/`pow` intrinsics need a cross-platform test suite (out of POC scope per brief) | open, must be built once before renderer work |
| 10 | Product-level solution for degenerate ultra-concentrated populations | aim variation, UX nudges | open (Stage 0.3 R3b, reproduced at compressed scale [measured]) |

---

## 13. Reproducible commands and artifact locations

All artifacts under `/tmp/dent-poc/conserved-material/` (recommended durable mirror:
`/workspace/conserved-material-poc/`):

| Experiment | Command (from the POC dir) | Result |
|---|---|---|
| E1 | `python3 exp1_conservation.py` | `results/e1_conservation.json` |
| E2 | `python3 exp2_threshold.py` | `results/e2_threshold.json` |
| E3/E4 | `python3 exp3_e4_invariant.py` | `results/e3_e4_invariant.json` |
| E5 (+E5b/E5c) | `python3 exp5_surface.py > logs/e5.log 2>&1`; see also `logs/e5b_fluffquant.log`, `logs/e5c_grazing.log` | `results/e5_surface.json`, `results/e5b_isosurface_agreement.json`, `results/e5c_grazing_split.json` |
| E6 | `python3 exp6_efficiency.py > logs/e6.log 2>&1` | `results/e6_efficiency.json` |
| E7 | `python3 exp7_terminal.py > logs/e7.log 2>&1` | `results/e7_terminal.json` |

Sources: `cm_rock.py` (engine), `streams.py` (histories), `modelA_stage03.py` (byte-identical Model A,
md5 `0e82227f77fe80dc843a847c7debc8a5`), `common.py`, `s01_c.py` (stub voxelizer), `logs/*` (raw),
`probe_hash.py`. Evidence-branch reference (read-only worktree): `/tmp/dent-stage03/stage-0.3/`.

Dependencies: none (Python 3.12 stdlib only). Not reproducible byte-for-byte across machines for
timings (see §6); identity/conservation results are exact integers and are reproducible byte-for-byte
[measured determinism of ledger identities].

---

## Final decision table

| Requirement | Model A (existing) | Conserved material approach | Better approach |
|---|---|---|---|
| No premature disappearance | **Equal** — cap bound already equivalent to q = (M₀−M_r)/N [derived; cap violations 0 in Stage 0.3, ledger violations 0 here] | **Equal** — guarantee enforced per-tap on every route [measured, 8 histories] | **Tie** (A′ ledger optional) |
| Accurate surface hits | **Defective** — 82 % of accepted hits sub-ISO on damaged rock; 23.8 % position agreement [measured] | **Defective identically** — same ray code (25.0 %) [measured] | **Neither** — both need the ISO-consistent contact fix (option-agnostic defect) |
| Localised damage | **Equal** — fully local carve [measured]; per-tap drama is a presentation matter [derived] | **Equal** — same carve form [measured, E4] | **Tie** |
| Natural fractures | Fragments emerge but 1.1 cells/component; death of cells unaccounted [measured] | Same fragmentation, mass additionally tracked [measured]; no dynamic fracture demo | **Tie** (neither demonstrates product-grade fracture; unknown) |
| Material accounting | Implicit only — cap + unbounded crumble tail (Stage 0.3 measured 6.8 % local tail) | **Explicit ledger, residual 0 at every milestone, every route audited [measured]** | **Conserved approach** — this is its one clear win at ~+9 %/tap cost |
| Performance | **0.35–0.50 ms/tap [measured]** | 0.379–0.544 ms/tap (+8–9 %) [measured] | **Model A** |
| Long-term maintainability | Simplest single-field engine [derived] | Thin separable ledger on same engine; debris/fragment policy complexity deferred [measured POC scope] | **Model A + thin ledger (A′)**; full Option C rejected at current scale (hier DDA 0.79× [measured]) |

**Bottom line**: adopt Model A′ (Model A + integer conserved ledger + ISO-consistent ray contact).
The conserved *mathematics* is sound and now measured on every code path; the conserved *architecture*
(massive debris/fragment machinery, hierarchical resolution) is not warranted by the evidence at
current scale, and its flagship component (hierarchy) measurably slowed things down. The most urgent
engineering debt — the sub-ISO ray-hit defect — belongs to the *existing* engine and must be fixed
regardless of which way the founder goes.
