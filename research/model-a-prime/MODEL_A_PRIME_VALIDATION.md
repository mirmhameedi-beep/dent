# DENT — Model A′ Technical Validation and Hardening

**Status:** Scratch investigation only. No changes were made to the Dent repository, Git history, PR #10, or any production system. All work lives under `/tmp/dent-poc/model-a-prime/` (mirrored to `/workspace/model-a-prime-poc/`).

**Date of experiments:** 2026-11-22 (see `results/*.json` meta blocks).

**Evidence labelling convention used throughout:**
- **[measured]** — produced by an executed experiment in this scratch tree; traceable to a JSON/log in `results/` or `logs/`.
- **[derived]** — arithmetic or logical consequence of measured values or of code inspection.
- **[estimated]** — extrapolation with stated assumptions; explicitly not a measurement.
- **[hypothesised]** — plausible, untested.
- **[unknown]** — not resolvable with the evidence available.

**Standing anti-claims honoured:** No billion-tap physical simulation was run (largest physical run: 8,000 compressed-lifetime taps; largest durable runs: N=10 and 5,000-tap cost benchmarks). No mass-ledger-equals-geometry claim is made. Hit-accuracy claims are tied exclusively to the independent reference implementations described in §4.

---

## 1. Executive summary

Model A′ — the existing Model A sparse-voxel engine plus (i) a thin exact integer material ledger with one authoritative per-tap budget, (ii) a corrected isosurface ray resolver, and (iii) a SQLite durable completion counter — was validated across six experimental parts.

**Key measured results:**

| Part | Headline result |
|---|---|
| A — Ray resolution | New resolver: **3,687/3,687 accepted hits agree with an independent fine-step reference**, 0 false hits, 0 false misses, 0 sub-ISO hits. 99.84 % within 0.15 cells on the coarse (0.05-cell) reference; **100 % after fine adjudication** — all 6 apparent outliers were defects in the *coarse reference*, not the engine; remaining engine-vs-fine error ≈ 10⁻¹⁰–10⁻⁹ cells. Old resolver on identical rays: 43.94 % within 0.15 cells, median 0.30, p99 17.87, max 38.10 cells, 79.1 % of hits on sub-ISO (invisible) material, 69 false hits, 892 false misses. **[measured]** |
| B — Per-tap budget | The suspected double-spend **is real and reproduced**: original conserved engine exceeded its per-tap allowance on **459/6,000 taps (max 1.210×)** under adversarial load while the cumulative checker logged **zero violations** (log-only, silent). Corrected single-budget engine: **0/6,000 over-budget**, max spend/q = 1.000, 0 spurious rollbacks; deliberate fault injection detected pre-commit and rolled back byte-identically. **[measured]** |
| C — Inventory vs geometry | The ledger does **not** guarantee a visible/connected rock. Measured separately: invisible (non-renderable) inventory ≤ 0.91 % through 8,000 compressed-lifetime taps; **visually (6-connectivity) the rock remains ONE connected object (share 0.9998–1.000, zero visible detached fragments)** in all three damaged states — the earlier "74,000 fragments" were severed-bond-graph artifacts; sub-ISO pressure inside the main component reaches **31.9 % of main mass** at the 8,000-tap point. **No proof of survival to the billionth tap exists.** **[measured for tested states; unknown beyond]** |
| D — Durable completion | SQLite store passed **10/10** crash/idempotency/concurrency tests including real SIGKILL mid-transaction, 6 crash points, 4-way final-tap race (exactly 1 winner), duplicate replay, post-completion rejection, no caller-supplied counter injection point. **[measured]** |
| E — Performance | E6 inconsistency root-caused: the two engines ran caps differing by ~50,000×. Consistent re-run on the authentic rock: Model A 0.349/0.499 ms/tap; Model A′ ledger 0.454/0.656 (+30 %/+31 %); with ISO resolver 0.657/0.813. Full-recount verification adds +0.83 ms/tap (validation-only). RSS 74–80.5 MB. Hierarchical-DDA block skipping measured **slower** (0.775×) in Python at this scale. **[measured]** |
| F — Original rock | **Recovered exactly**: 151,553 cells / 34,816,588 legacy density sum from the Stage 0.3 checkpoint `state_10000.pkl`; the POC substitute (147,908 / 33,977,655) is retired. All headline experiments were re-run on the authentic rock. **[measured]** |

**Final recommendation: B — Model A′ is promising but requires further investigation before any architecture freeze.** The two engineering pillars (exact ledger with a real single budget; renderer-consistent ray resolution; durable completion) are demonstrated at reduced scale. The product-critical open questions are: (1) the visible/connected/hittable survival guarantee to exactly tap 10⁹ (as opposed to a positive ledger balance) is **not proven** and is not guaranteed by the current design; (2) fragment/debris rendering and hittability policy is undecided; (3) the ledger costs ~30 % per tap in Python and the ISO resolver a further ~24–45 %, and production-engine validation overhead is not yet subtracted; (4) nothing has been measured at, or credibly extrapolated to, billion-tap state evolution (§11).

---

## 2. Architecture under investigation

Model A′ = **Model A (unchanged physics core) + three thin layers**:

1. **Exact integer material ledger** (`maprim_rock.MaprimRock`): fixed-point dfix units (legacy density × 65,536). Identity `M0 == main_field + debris + fines + consumed + burned` checked per tap before commit. One authoritative per-tap budget `q_tap = (M0 − Mr) // N` governs **all** irreversible removal (carve take, crumble residuals, shed/fines) via `budget_left`, with pre-commit validation and journal-undo rollback. `consumed` and `burned` are **accounting categories** for material no longer physically present (§6.4).
2. **Renderer-consistent ray resolver** (`resolve_iso`): node-plane DDA walk over trilinear-interpolated density, exact cubic evaluation per segment, bisection refinement, first crossing of `DENS_ISO = 120` — the same isosurface definition the renderer uses. Misses are misses; the only non-ray behaviour retained is *attribution* of a hit's damage to the dominant interpolation node (argmax over the 8 crossing-block nodes, guaranteed ≥ ISO) — impossible to redirect a miss into a hit.
3. **Durable completion store** (`store.py` + `worker.py`): SQLite WAL, `synchronous=FULL`, `BEGIN IMMEDIATE`; authoritative counter = tap-row count; completion flag + terminal event committed in one transaction; downstream publication idempotent and recoverable.

Engines under test: `src/modelA_stage03.py` (byte-identical Model A baseline, unmodified), `src/cm_rock.py` (original conserved engine, unmodified — audit target), `src/maprim_rock.py` (Model A′). Independences used as references: `ref_trilerp` (separate trilinear implementation, max diff vs engine trilerp = 0.0 **[measured]**, `results/smoke_test.json`) and `first_iso_reference` (0.05-cell / 0.002-cell fine-step scanner sharing no ray code with the engine).

All experiments use the **authentic recovered pristine rock** (Part F): 151,553 cells, 34,816,588 legacy sum, M0 = 2,281,739,911,168 dfix, `pristine_state_sha256 = 21b94288…a9f69` **[measured, `results/f_initial_rock.json`]**.

**Compressed-lifetime recipe** [derived]: a billion-tap lifetime cannot be physically simulated; per-tap allowance is accelerated by `alpha = q_legacy / 15.33` (used consistently at alpha ≈ 98.73 for Part B/C) or by running at the true billion-α (0.0019738, Part E). These measure **costs and failure modes**, not billion-scale evolution.

---

## 3. Test methodology

- **Independent references everywhere.** Ray truth = independent fine-step scanner on `ref_trilerp` (separate implementation, 0.05-cell step; 0.002-cell for adjudication of disagreements). Engine never its own reference. Interpolation models proven identical first (max abs diff 0.0).
- **Authentic damaged states.** Part A/B/C run on states produced by real `tap_transaction` damage on the authentic rock: D1/D1b bores, D2 clustered/fragments, D3 hostile (2,000-tap), plus milestone runs A_rot / B_distributed at 1,000–8,000 compressed taps (`renders/state_*.pkl`).
- **Ray battery:** 3,856 rays in 5 families — F1 pristine surface (300), F2 crater floors, F3 bore-axis/through, F4 newly exposed interiors, F5 grazing/oblique — each ray executed through all three resolvers (new, old, independent reference).
- **Adversarial accounting:** Part B runs at alpha = 98.73 (≈ 3,270× the billion-α of 0.0019738) so that budget-clamp edges and debris routing fire on most taps; 6,000 accepted taps of 6,245 launched on the B_distributed recipe.
- **Durability:** real subprocesses with engineered crash points and real `SIGKILL`; every test verified with `check_consistency` against durable state; evidence DBs retained (`db/d*.db`).
- **Reproduced historical figures.** The earlier POC's 27.69 % / 26.31-cell numbers were not re-verified bit-for-bit (different rock and ray set); the equivalent geometry was re-measured fresh on the authentic rock instead **[derived limitation]**.

---

## 4. Ray-resolution findings and metrics (Part A)

### 4.1 Target: ≥ 99 % of accepted hits within 0.15 voxel cells of the independent first-ISO crossing

| Metric | New resolver (Model A′ `resolve_iso`) | Old resolver (Model A DDA accept-density>0) |
|---|---|---|
| Test rays | 3,856 | 3,856 |
| Accepted | 3,687 (100 % of reference-accepted) | 2,864 |
| Rejected | 169 (all true misses) | — |
| False hits | **0** | 69 |
| False misses | **0** | 892 |
| Hits on sub-ISO (invisible) material | **0** | 79.12 % |
| Median error (cells) | 0.0 | 0.3009 |
| p95 | 0.0 | 6.672 |
| p99 | 0.0 | 17.871 |
| Max | 6.083 (see 4.2) | 38.100 |
| Within 0.15 cells | **99.837 % → 100 %** after adjudication | 43.936 % |

**[measured, `results/a_surface.json`, `results/a_final_stats.json`]**

Verdict-and-position agreement with the independent reference held for **every one of the 3,687 accepted hits**; the 169 rejections include all reference-rejected rays (no missed surfaces, no redirection into bores/openings — F3 bore-axis families exercised these, e.g. 90/500 and 250/500 correctly rejected).

### 4.2 Outlier adjudication — 6 remaining >0.15-cell cases

All 6 were re-measured against a 0.002-cell fine reference:

- Engine error vs fine reference: **6.7×10⁻¹² … 2.2×10⁻⁹ cells** (i.e. numerically perfect for this purpose).
- The coarse (0.05-cell) reference had skipped thin sub-ISO slivers by the fine scanner's own admission (`a_outlier_adjudication.json`, each marked `engine_correct_coarse_ref_skipped_feature`).

**Conclusion [measured]:** the 99.837 % figure was a limitation of the first reference, not the engine. Against the best available independent reference, **accepted-hit placement is exact to ≈ 10⁻¹⁰ cells and 100 % within 0.15 cells on this battery**. Scope: one rock, 3,856 rays, 5 families; this is not an exhaustive proof over all impact histories **[hypothesised generalisation]**.

### 4.3 No-redirection guarantees [derived from code + measurement]

- The resolver has **no nearest-occupied-voxel fallback, no snap, no memory of previous hits** (the earlier POC's `tap_iso` snap fallback was removed; replaced with dominant-node *attribution*, which only selects where an already-accepted hit deposits damage and cannot convert a miss into a hit).
- Miss handling measured: bore-axis/through rays (F3) yielded rejections exactly where the reference rejected; 0 false hits overall.

---

## 5. Material-budget audit and tests (Part B)

### 5.1 Does the original implementation actually allow budget reuse? — Yes.

`cm_rock.py` (unchanged) was audited line-by-line (grep record in `results/b_budget_audit.json → b5_writer_audit`) and run adversarially:

- `_apply_carves()` establishes a local carve budget; `debris_after_tap()` then creates a **fresh** allowance from `self.q_tap` and spends it on debris fines routing in the same tap.
- `_check_invariant()` **logs** violations; it does not roll back. With over-budget caused by the double allowance, the cumulative check `consumed > n·q` can still pass (per-tap overshoot self-corrects within the cumulative line).

### 5.2 Reproduction (6,000 accepted taps, alpha 98.73, dispersed stream)

- **459 of 6,000 taps** exceeded the per-tap allowance; max spend 120,025,679 dfix vs q_tap 99,188,729 dfix = **1.210× q**; mean 55.9 M dfix. `violations_allowance = 0` — the checker logged **nothing** while the per-tap invariant was being violated hundreds of times. **[measured]**
- The cumulative `consumed ≤ n·q` line was not breached in this run (335.3 G vs 595.1 G dfix at n=6000) — i.e. the dangerous behaviour is *invisible by design of the old checker*, exactly the failure mode Part B was designed to expose.

### 5.3 Does one shared budget resolve it? — Yes.

Corrected engine (`maprim_rock.MaprimRock`), same rock, same stream, same alpha:

- 6,000 accepted taps: **0 over-budget taps**, max spend = q exactly (1.000×), 0 rollbacks needed in normal operation, ledger identity clean. **[measured]**

### 5.4 Can any code path bypass the budget? Rollback sufficiency?

- All irreversible sinks (`_route` carve residuals, `_route_crumble_residuals`, `_shed_tap`) draw from the **same** `tx["budget_left"]` clamp; crumble candidates are only processed against remaining budget.
- Fault injection (deliberate): (i) injected `consumed` inflation → violation `ledger_identity, drift = 3,769,171,702 dfix` detected **pre-commit**; (ii) transaction-counter inflation → `per_tap_budget, spent 6,794,396,721 vs budget 99,188,729`. Both cases: `ok=false`, complete journal-undo rollback, **state hash byte-identical** to pre-tap (`bd0dec21a2a51ab308628a85`), subsequent clean tap accepted. **[measured, `results/b_budget_audit.json → b4_rollback`]**
- Checked-bypass paths not found in the audited code; a full formal audit of future code is out of scope **[unknown for future code]**.

---

## 6. Inventory versus visible-geometry analysis (Part C)

### 6.1 Definitions measured separately

| Class | Definition | 1,000-tap | 8,000-tap (A_rot) |
|---|---|---|---|
| A — Inventory | `M0 − consumed − burned` (ledger) | 34.13 M legacy | 29.68 M |
| B — Renderable | mass in components with ≥ 1 cell ≥ DENS_ISO | 33.25 M | 24.28 M |
| B′ — Invisible | inventory mass not in B | 194.7 k (0.57 %) | 269.3 k (**0.91 %**) |
| C — Hittable (main) | exterior-cell mass of renderable main | 243.7 k | 189.3 k |
| C — Hittable (fragments) | 1.96 M | 1.61 M | |
| D — Main connected object | largest renderable component | 13.16 M | 9.08 M |

**[measured, `results/c_geometry.json` — compressed-lifetime alpha = q/15.33, N\*=20000; duplicated 8,000-tap row in the artifact is a recording overlap, values identical]**

### 6.2 The bond graph vs what visitors actually see — a material correction

The engine's `components()` is a **severed-bond graph**. Re-partitioning the *same* states by plain 6-connectivity of visible material **[measured, `results/c_visual_partition.json`]**:

| State | Bond components | Largest bond share | Visual components | Largest visual share | Visible detached fragments |
|---|---|---|---|---|---|
| D1 bores (5,000) | 80,303 | 0.364 | **20** | **0.9998** | **0** |
| D2 fragments (6,000) | 78,093 | 0.360 | **14** | **0.9998** | **0** |
| D3 hostile (2,000) | 89,492 | 0.371 | **18** | **0.9998** | **0** |

The "74,000+ visible fragments" reported earlier were severed-bond artifacts of the internal graph, not physical objects. Under visual connectivity the rock remained **one connected object** (with a handful of small visual satellites: 14–20 components) in every damaged state tested.

### 6.3 Adversarial fragment kill [measured]

A 1-cell fragment was deliberately targeted: killed in **1 tap**; ledger stayed above `Mr` (4,546,590 legacy); the other ~74,000 bond components were untouched; visual components remained 74,094→74,094 in bond terms. Hittability of tiny fragments is real, but their prominence in the graph is an accounting artifact, not a visual one.

### 6.4 Answer to the standing question: what do `consumed` and `burned` mean?

- **`consumed`** — the ledger category for material **irreversibly removed from the physical scene** by ordinary per-tap physics (the clipped carve take, crumble residuals beyond what is re-deposited, shed fines). It is spent against the per-tap allowance q.
- **`burned`** — the ledger category used **only** by the terminal event: the one-time bulk transfer of all remaining physically-represented material at exactly the billionth accepted tap (`burned = M0 − consumed` at completion).
- **Neither is physically retained material.** Both are accounting categories representing material **no longer present in the physical world**. Material that *is* still represented (main field, fragments, debris, fines entries backed by spatial records) is never counted under either.

### 6.5 Direct answer: can we truthfully guarantee the rock remains a visible, hittable object until exactly the billionth tap?

**No — not on current evidence, and the mass ledger does not by itself provide that guarantee.**

- What is proven [measured]: exact integer conservation of the ledger; ≤ 0.91 % invisible inventory through 8,000 compressed taps; visual one-ness through the tested damaged states; per-tap consumption bounded by q.
- What is *not* proven: that no sequence of 10⁹ valid taps can drive the **connected visible main object** below a meaningful threshold earlier (the ledger can remain positive while visible material becomes glacial, disconnected, or sub-ISO). Sub-ISO pressure inside the main component was already **31.9 % of main mass** at the 8,000-tap point in A_rot [measured; behaviour beyond tested states unknown].
- What the design still needs (identified, not implemented): a **minimum connected visible-material reserve** checked as a first-class invariant (not just mass ≥ Mr), an explicit decision on whether debris/fines are rendered/hittable, and a prohibition on silently converting visible representation into invisible inventory entries.
- The survival guarantee and the redirection guarantee remain separate qualifications: even with a perfect ledger, whether a particular ray sequence can generate 10⁹ *accepted* taps is a different question [derived].

---

## 7. SQLite completion and crash-recovery results (Part D)

Store: `store.py` — authoritative count = tap-row count; no caller-supplied counter parameter exists (injection attempt `claim_tap(n=10)` → `TypeError`, measured); completion flag and terminal event committed in **one** transaction; idempotency by request uuid; publication (`published` flags) is a separate, re-derivable step. Engine: SQLite WAL, `synchronous=FULL`, `busy_timeout=30000`.

**10/10 tests passed.** [measured, `results/d_durable.json`, DBs in `db/`]

| # | Test | Setup | Expected | Actual | Evidence |
|---|---|---|---|---|---|
| 1 | `crash_before_txn` | worker killed (exit 137) before any tap txn | no partial rows; restart normal | 0 rows; restart reaches 10/10, completed | `db/d1_crash_before.db` |
| 2 | `crash_in_txn_pre_commit` | row inserted, death **before** COMMIT | insert rolled back | 0 rows; restart fills 1..10 | `db/d2_crash_precommit.db` |
| 3 | `crash_after_commit` | death after 5th COMMIT | committed rows persist; uuid replay identical | 1 row persists; replay returns same n, no new row | `db/d3_crash_postcommit.db` |
| 4 | `crash_during_terminal` | tap 10 commits completed=1, death before event row; recovery worker also killed mid-recovery | completed stays 1; post-completion tap rejected; exactly ONE terminal event after recovery rerun | measured: completed=1, claims rejected (`completed`), recovery rerun → exactly 1 terminal event, rows=10 | `db/d4_crash_terminal.db` |
| 5 | `crash_before_publication` | terminal event written, death before publish flags | recovery publishes exactly once, payload intact | unpublished 1→0 after recovery; payload `{"action":"disintegrate_all"}` ×1 | `db/d5_crash_before_pub.db` |
| 6 | `crash_during_recovery` | recovery SIGKILLed mid-run, then rerun | consistent state throughout, rerun completes | mid-state and final both consistent, exactly 1 event | `db/d6_crash_during_recovery.db` |
| 7 | `real_sigkill_mid_transaction` | parent sends real SIGKILL at 120 ms inside a tap txn | no partial commit | rows=10 contiguous, completed, consistent | `db/d7_sigkill_mid_txn.db` |
| 8 | `concurrent_final_tap_race` | 4 processes race for the final tap, distinct uuids | exactly 1 winner | 1 winner (`race0-k0`), 1 event, rows=10 | `db/d8_concurrent_final.db` |
| 9 | `no_caller_supplied_counter` | attacker-controlled n injection attempted | no parameter to bypass; state counter authoritative | `TypeError: unexpected keyword 'n'`; normal claim → n=10 | `db/d9_no_bypass.db` |
| 10 | `terminal_idempotency_and_restart` | same uuid thrice; `ensure_terminal_event` twice; restart; taps after completion | one row; one event; post-completion claims rejected; `n>N` never creates rows | measured: duplicates return same n; exactly 1 event; post-completion claim rejected; 0 rows for n>N | `db/d10_idempotent.db`, `db/d11_terminal_restart.db` |

Distinguishing layering verified: **durable completion state** (atomic) → **terminal event row** (idempotent, recoverable) → **publication flags** (idempotent, recoverable) → **visual disintegration rendering** (out of scope here, downstream of publication). A crash anywhere after the completion commit can delay or re-derive downstream steps but cannot lose, duplicate, or pre-trigger completion **[measured]**.

Scope note: tested at N=10 with real subprocess semantics; the transaction shape is N-independent (counter is row-count based), but no billion-scale DB sizing/load test was run [derived boundary].

---

## 8. Performance reconciliation (Part E)

### 8.1 E6 inconsistency — root cause [measured, `results/e_perf.json → meta.e6_inconsistency`]

- Conserved-side constructor: `ConservedRock(N=20000)` on the **stub rock** → per-tap allowance q = **1,477.02** legacy/tap.
- Model A side ran cap = **0.029540415** legacy/tap.
- The reported "billion-scale allowance" 0.029540415 / alpha 0.00197456 belongs to the **original** rock cap (0.030269998 / 15.33), not what the conserved engine actually ran.
- Consequence: the two sides ran caps differing by **≈ 50,000×**. At billion-α demand level the caps rarely bind, so the CPU *timings* were indicative but the documented configuration was inconsistent and the comparison not configuration-matched. Verdict: the E6 table was **not valid as a matched configuration**; re-measured below.

### 8.2 Consistent re-run (identical caps, authentic rock, 5,000 accepted taps of identical hit streams)

`N = 10⁹, Mr = 4,546,590.0 legacy (2 %+crumble-slack rule), q_tap = 1,983 dfix = 0.0302582 legacy/tap, alpha = 0.0019738 vs reported 0.00197456 (0.04 % apart) — configuration now consistent.`

| Configuration | A_concentrated ms/tap | B_distributed ms/tap | RSS MB | modified cells/tap |
|---|---|---|---|---|
| Model A baseline | **0.349** (2,865/s) | **0.499** (2,006/s) | 74.4 / 80.5 | 33.57 / 33.15 |
| Model A′ + ledger (incremental verify) | 0.454 (**+30.1 %**) | 0.656 (**+31.5 %**) | 80.5 | same |
| Model A′ + ledger + ISO resolver | 0.657 (+45 % vs ledger) | 0.813 (+24 % vs ledger) | 80.5 | 36.42 / 33.68 |
| Model A′ + ledger, full-recount verify (validation only) | 1.280 (+0.83 ms vs incremental) | — | 80.5 | same |

**[measured]** These are **short-run cost measurements under compressed-α conditions**, not billion-scale throughput forecasts [explicitly labelled].

- Ledger overhead is bounded and stream-dependent (~0.11–0.16 ms/tap in Python); a compiled (C/Rust/Go) ledger would shrink this proportionally [estimated].
- Full-recount per-tap verification (+0.83 ms/tap) is a *validation-mode* cost used to prove incremental correctness; production would use incremental spot-audit [derived from measured delta].
- Ray cost within the ISO resolver: 0.237–0.451 ms/tap vs 0.070–0.157 for the old DDA — the price of renderer-consistent surface truth [measured].

### 8.3 Hierarchical-DDA supplement (Option C block-skipping)

Authentic-rock 4,000-tap damaged state, 600 rays: plain DDA **0.0699 ms/ray** vs hierarchical block-skipping **0.0901 ms/ray** = **0.775× (slower)**, 0 contact mismatches, 76/979 blocks empty. **Option C block-skipping does not pay off in Python at ~152 k-cell scale** [measured, `results/e_hier_dda.json`]. A coarser, lower-level language implementation could reverse this; not tested [hypothesised].

---

## 9. Original voxelizer / reproducibility findings (Part F)

- **Recovered, not substituted.** The original initial rock was reconstructed from the Stage 0.3 evidence checkpoint `histories/B_distributed/state_10000.pkl` (the `occ_*` occupancy block is the pristine state at t=0 in that run). Script: `src/recover_initial_rock.py`. [measured, `results/f_initial_rock.json`]
- Verified: **151,553 cells; 34,816,588 legacy density sum — exact match** to the original Stage 0.3 record (cells match, sum match both flags true). Checkpoint-vs-reconstruction diff: 17,911 cells differ (those are the 10,000 compressed taps of damage in that history — the reconstruction strips applied damage; 0 cells only-in-checkpoint at the occupancy level).
- `pristine_initial.pkl`, sha256 `21b942883d67134fb799a279c93209f20b0d145f83df87c66a50cedb2a9a9f69`. **[measured]**
- The earlier POC substitute (147,908 / 33,977,655; 2.44 % cell-count gap) is **retired**; every headline experiment in this validation (A, B, C, E) ran on the authentic rock. The exact original voxelizer source `s01_c.py` was still not present in the evidence branch; recovery is from its durable *output* — reproduction is therefore exact for the state, while voxelizer *code* provenance remains **[unknown]**; recorded so no silent substitution is claimed.

---

## 10. Complete pass/fail/inconclusive status table

| Area | Required outcome | Status | Evidence & limitations |
|---|---|---|---|
| Visible-surface ray resolution | Pass / Fail / Inconclusive | **Pass** | 3,687/3,687 vs independent ref; §4 [measured] |
| Hit-position accuracy | Measured error statistics | **See §4** | median 0, p95 0, p99 0, max ≈ 10⁻⁹ cells vs 0.002-cell ref; 100 % within 0.15 after adjudication [measured] |
| Miss rejection and no redirection | Pass / Fail / Inconclusive | **Pass** | 0 false hits; F3 bore-axis rejections match reference; no snap/redirect code paths [measured + code audit] |
| One shared per-tap material budget | Pass / Fail / Inconclusive | **Pass** | flaw reproduced (459/6,000 @1.21×, log-only); corrected: 0/6,000, max/q=1.000; rollback proof §5 [measured] |
| Exact material accounting | Pass / Fail / Inconclusive | **Pass** | identity verified pre-commit; fault injection detected; determinism two-run hash-identical [measured] |
| Visible and hittable geometry guarantee | Proven / Not proven | **Not proven** | ≤0.91 % invisible through 8,000 compressed taps; no billion-tap proof; sub-ISO 31.9 % pressure at 8,000 (§6) [measured subset / unknown beyond] |
| Connected physical object guarantee | Proven / Not proven | **Not proven** | visually one object (share 0.9998–1.0) in tested states; no guarantee mechanism exists in the design yet (§6.5) |
| Durable accepted-tap counter | Pass / Fail / Inconclusive | **Pass** | row-count authority; no caller bypass; 10/10 §7 [measured at N=10 scale] |
| Exactly-one-billionth completion | Pass / Fail / Inconclusive | **Pass (N=10 proxy)** | atomic completion+terminal in one txn; N-independent shape; billion-scale load untested [measured proxy / derived] |
| Crash recovery | Pass / Fail / Inconclusive | **Pass** | 6 crash points + real SIGKILL, all consistent (§7) [measured] |
| Duplicate and concurrent request safety | Pass / Fail / Inconclusive | **Pass** | uuid idempotency (thrice-replayed); 4-way race → 1 winner [measured] |
| Performance overhead | Measured | **Measured** | +30/+31 % ledger; +24/+45 % ISO resolver; hier-DDA 0.775× (§8) [measured] |
| Original initial-rock reproducibility | Recovered / Not recovered | **Recovered (exact state)** | §9; voxelizer code provenance unknown [measured/unknown] |

---

## 11. Known limitations

1. **No billion-tap physical simulation.** Max physical run: 8,000 compressed-lifetime taps (alpha ≈ 98.7) / 5,000 billion-α cost taps. All lifetime behaviour beyond that is [unknown].
2. **Survival guarantee is a ledger guarantee only.** Visible/hittable/connected survival to tap 10⁹ is unproven and not enforced by design (§6.5). The product question "one visibly intact rock at tap N−1" is open.
3. **Fragment/debris representation is not rendered and not hittable in the POC.** Debris/fines exist as ledger entries; their visual honesty and their interaction policy are product decisions deliberately left open (§6, per brief).
4. **Scale ceilings.** SQLite concurrency tested with 4 workers and N=10 (correctness-focused). Python single-process throughput (≈ 1.2–2.9 k taps/s measured at compressed-α) is far below the real product's expected peak tap rate; throughput engineering is a later, separate problem [measured cost / unknown product requirement].
5. **Rendering-consistency is definition-level, not pixel-level.** Resolver and assumed renderer agree on `DENS_ISO` trilinear semantics (proven identical to an independent implementation); no image-space comparison was made [derived].
6. **Single machine, single process for physics.** No multi-writer physical-state concurrency was tested (only the SQLite completion layer is multi-process-safe).
7. **Accelerated-α results measure cost/failure modes, not geometric lifetime evolution** — e.g. the 31.9 % sub-ISO figure is a compressed-α artifact whose real-rate trajectory is [unknown].
8. Reproduced historical POC numbers (27.69 % / 26.31 cells) were superseded by fresh measurements on the authentic rock, not re-derived under the original POC's configuration [stated for honesty].

---

## 12. Final recommendation

**B — Model A′ is promising but requires further investigation. It is NOT ready for an architecture freeze.**

Justified by: exact ledger under a single authoritative budget with working pre-commit rollback **[measured]**; renderer-consistent ray resolution at reference-grade accuracy **[measured]**; durable, crash-safe, idempotent completion **[measured]**; genuine ~30 % (+24–45 % resolver) per-tap overhead with a clear path to reduction **[measured/estimated]**.

**Precise remaining blockers (in priority order):**

1. **Design and prove the visible/connected/hittable reserve invariant** — extend M(n) ≥ M(n−1) − q with a first-class *connected visible main-object* floor checked pre-commit; without it, no truthful product guarantee exists (§6.5).
2. **Decide the fragment/debris/fines rendering and hittability policy** — mechanical options identified; consequences (object-population growth vs honest invisibility) quantified only at compressed-α.
3. **Validate the completion store at production scale** — same transaction logic, real N-local benchmark, realistic concurrency, and a declared capacity allowance (billion-tap DB sizing estimate exists at ~40–45 GB worst case from earlier derivation; unverified here [prev-Ctx/estimated, not re-measured]).
4. **Subtract consumer-side cost from the 30 % ledger overhead** — production will batch taps and reuse rendered frames; the measured single-tap cost includes no such amortisation [estimated].
5. **Long-horizon behaviour** — a real-rate multi-day simulation (or a validated extrapolation model) before any claim about rock appearance near tap 10⁹ [hypothesised].

Not recommendation C: no evidence of a *fundamental* flaw was found; every reproduced defect (double budget, coarse-resolver mismatch, config inconsistency, substitute rock) was repaired in-scope and the repaired design held under adversarial testing.

---

## 13. Exact commands required to reproduce the experiments

All commands run from the scratch root `P=/tmp/dent-poc/model-a-prime` (mirror: `/workspace/model-a-prime-poc`). Python 3.12, no third-party deps. The Stage 0.3 checkpoint source `/tmp/dent-stage03/stage-0.3/histories/B_distributed/state_10000.pkl` must exist for Part F.

```bash
cd /tmp/dent-poc/model-a-prime/src

# Part F — recover + verify authentic pristine rock (writes src/pristine_initial.pkl)
python3 recover_initial_rock.py

# Smoke: construction, ref_trilerp equivalence, resolver-vs-reference agreement
python3 smoke_test.py                      # → ../results/smoke_test.json

# Part A — ray battery (damaged states built on authentic rock)
python3 expA_surface.py                    # → ../results/a_surface.json, ../renders/state_*.pkl
python3 adjudicate_outliers.py             # fine re-reference of err>0.15 rays (subset)
python3 adjudicate_all.py                  # → ../results/a_outlier_adjudication.json, a_final_stats.json

# Part B — budget audit (original reproduction, corrected engine, rollback proof)
python3 expB_budget_audit.py               # → ../results/b_budget_audit.json

# Part C — inventory vs geometry + visual partition supplement
python3 expC_geometry.py                   # → ../results/c_geometry.json
python3 supC_visual_partition.py           # → ../results/c_visual_partition.json (needs expA renders)

# Part D — durable completion + crash recovery (subprocesses + SIGKILL; writes db/)
python3 expD_durable.py                    # → ../results/d_durable.json, ../db/d*.db

# Part E — reconciled performance + hierarchical DDA supplement
python3 expE_perf.py                       # → ../results/e_perf.json
python3 supE_hier_dda.py                   # → ../results/e_hier_dda.json

# Determinism — two identical pipeline runs, hash compare (recorded in results/det_check.json)
#   engine run ×2 with hostile stream seed 4242, 1500 taps; hashes 354bdb0b… identical.
worker.py and store.py are exercised by expD_durable.py (no standalone invocation needed).
```

Wall times (measured): smoke ≈ 1 min; A ≈ 65 s + adjudication; B ≈ 24 s; C ≈ 26 s; D ≈ 2–3 min; E ≈ 2–4 min. Total full reproduction ≈ 15–20 min.

---

## 14. List of all generated evidence files

```
/tmp/dent-poc/model-a-prime/
├── MODEL_A_PRIME_VALIDATION.md            ← this report
├── results/
│   ├── f_initial_rock.json                Part F  — exact recovery record + sha
│   ├── smoke_test.json                    construction + ref_trilerp + resolver basics
│   ├── a_surface.json                     Part A  — 3,856-ray battery (new/old/ref)
│   ├── a_outlier_adjudication.json        Part A  — 0.002-cell re-reference of 6 outliers
│   ├── a_final_stats.json                 Part A  — post-adjudication final stats
│   ├── b_budget_audit.json                Part B  — 459/6000 reproduction, correction, rollback proof, writer audit
│   ├── c_geometry.json                    Part C  — A/B/C/D masses at milestones + fragment-kill test
│   ├── c_visual_partition.json            Part C  — bond vs visual partition (80,303→20 components)
│   ├── d_durable.json                     Part D  — 10/10 crash/idempotency/race tests
│   ├── e_perf.json                        Part E  — E6 root cause + consistent re-run
│   ├── e_hier_dda.json                    Part E  — hierarchical DDA 0.775× (slower)
│   └── det_check.json                     determinism — 2× identical state hashes
├── renders/state_D1_bores|D1b_deep_bores|D2_fragments|D3_hostile(…).pkl(+_summary.json), state_C_*.pkl
├── db/d1…d11*.db                          Part D — retained SQLite evidence databases
├── logs/a_surface.log, a_adjudicate*.log, c_geometry.log
└── src/
    ├── maprim_rock.py                     Model A′ engine (ledger + ISO resolver + transaction)
    ├── modelA_stage03.py                  Model A baseline (byte-identical copy, unmodified)
    ├── cm_rock.py                         Original conserved engine (unmodified audit target)
    ├── store.py / worker.py               Durable completion store + crash-point worker
    ├── streams.py, common.py, s01_c.py    Streams, helpers, stub voxelizer (copy)
    ├── recover_initial_rock.py            Part F recovery
    ├── pristine_initial.pkl               Authentic pristine rock (sha 21b94288…)
    ├── smoke_test.py
    ├── expA_surface.py, adjudicate_outliers.py, adjudicate_all.py
    ├── expB_budget_audit.py
    ├── expC_geometry.py, supC_visual_partition.py
    ├── expD_durable.py
    └── expE_perf.py, supE_hier_dda.py
```

---

*Prepared as an isolated feasibility validation. No Dent repository / application / production modifications, commits, pushes, or PRs were made for this work.*
