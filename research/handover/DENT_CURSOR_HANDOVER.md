# DENT — Complete Handover Package for Cursor

**Package date:** 2026-11-22
**Prepared by:** Mistral investigation sessions (Nov 2026)
**Purpose:** Transfer the full Dent physical-engine research corpus — evidence, engines, scripts, results, databases, logs — so development can continue in Cursor with no loss of context.
**Delivery:** committed to the research-only branch `research/dent-cursor-handover-2026-11-22` (base: `vibe/stage03-artifacts-a7e03e`), under `research/`, checksummed in `MANIFEST.md`. PR #10 (Stage 0.3 evidence) remains open and untouched.

> **Scope discipline for the incoming engineer:** everything in this package is scratch research. Nothing here was ever merged into the Dent application, no commits/pushes/PRs were made for this work, and the production system was never touched. Read `CONSERVATION_ENGINE_INVESTIGATION.md` and `model-a-prime/MODEL_A_PRIME_VALIDATION.md` before running anything.

---

## 1. What Dent is intended to become

Dent is **one shared physical rock** — a single canonical stone, hit by millions of visitors worldwide, carved forever, disintegrating at exactly the **1,000,000,000th accepted tap**.

AApp Store pitch in one line (from `README.md`): *a multi-generational group project with no purpose.*

Fixed product requirements (non-negotiable):

1. One shared rock — not per-user copies.
2. A tap must hit the **actual current visible surface**.
3. The exact hit location determines where damage occurs.
4. Concentrated vs distributed histories must produce different physical outcomes.
5. Repeated impacts inside a crater must hit its current floor/walls.
6. Newly exposed internal surfaces are genuine hittable surfaces.
7. Fractures/fragments emerge from accumulated damage, not predetermined stage images.
8. Untouched regions must not be artificially damaged as the global counter grows.
9. A ray through empty space is **rejected — never redirected** to an old hit or nearby surface.
10. The rock and its visible material must not disappear before exactly 10⁹ accepted taps.
11. At exactly the billionth tap, all remaining material disintegrates.
12. Presence/achievements/sponsorship/analytics stay independent of the physical engine.
13. Accepted taps vs rejected attempts is an absolute distinction.

Determinism is a core engineering value: same initial rock + same ordered accepted impacts + same engine version ⇒ identical state (fixed-point integer accounting).

## 2. Existing application architecture and production environment

Repository: `mirmhameedi-beep/dent` (this is the **application**, fully separate from the research packages included here).

```
app/       SwiftUI iOS app (iOS 17+, XcodeGen, SceneKit 3D stone, offline queue in
           UserDefaults, Keychain device identity, haptics/Wall/pull-to-refresh)
backend/   single-file FastAPI service (backend/main.py, 192 lines) over SQLite:
           GET /stone   — newest 400 dents worldwide (front loading + 3D positions)
           POST /tap    — idempotent tap (client UUID dedup), global counter, one-billion ceiling
           GET /wall    — Wall of contributors
           GET /static  — public site: same 3D stone on <canvas> with identical math
           allow()      — per-key rate limiting (memory-bounded as of PR #9)
deps:      fastapi 0.115.6, uvicorn 0.34.0, pydantic 2.10.4 (stdlib sqlite3 storage)
```

- **Web renderer is developed and tested first** (canonical); iOS/SceneKit parity follows later (coordinate contract v3 exists in the Stage 0.3 bundle).
- Physical state canon: page renders use 3D positions persisted per dent; the web stone and app stone show the same object.
- Production environment: **Railway** (deployed backend). *No production access is granted in this handover; no production inputs appear in this package.* The SQLite databases in `model-a-prime/db/` are synthetic N=10 test fixtures, not production data.

## 3. Current Git repository and production branch

- Working branch / production base: **`vibe/dent-mvp-a7e03e`** (the only branch merged to so far).
- Evidence branch (Stage 0.3, see §5): **`vibe/stage03-artifacts-a7e03e`** — must remain **UNMERGED** (PR #10).
- Repo state at packaging: clean tree, latest commit `09e9270 "Merge pull request #9 from mirmhameedi-beep/vibe/rate-limit-bound-a7e03e"`.

## 4. Reliability work already merged (PRs #1–#9)

| PR | Content |
|---|---|
| #1 | Dent MVP: SwiftUI tap app + FastAPI global counter |
| #2 | Stationary rock (no auto-rotation, inertial drag) |
| #3 | Backend tap idempotency (client UUID dedup) |
| #4 | iOS tap submission idempotent + reliable (offline queue flush) |
| #5 | Backend one-billion dent completion ceiling enforced |
| #6 | Web: idempotent persistent tap pipeline with completion handling |
| #7 | Web: wall refresh immediately after each acknowledged tap |
| #8 | Web: favicon (404 fix) |
| #9 | Backend: rate-limit table memory bound + concurrency/high-cardinality tests |

Status: idempotent tap pipeline (client→web→backend), completion ceiling, and rate-limit hardening are all **merged and in production**. What is *not* built yet: the real shared physical engine (deep geometry, craters, fragments) — that is what the included research targets.

## 5. Stage 0.3 investigation and PR #10 (must remain unmerged)

**PR #10** — https://github.com/mirmhameedi-beep/dent/pull/10 — `Stage 0.3 — experimental evidence bundle`, head `vibe/stage03-artifacts-a7e03e`, base `vibe/dent-mvp-a7e03e`, **OPEN**, additive read-only evidence under `stage-0.3/` (no app code modified).

Contents: `REPORT.md` (18 sections), 36 pure-stdlib scripts, 19 result JSONs, 62 logs, 112 PNG renders, per-history checkpoints (`state_<accepted>.pkl`) for five impact histories A–E plus a 60M distributed run, Stage 0.2 report/context/parity fixtures.

Headline (as stated in the PR — the bundled reports carry the full evidence labels):
- Early depletion was a **pure per-tap mass-budget effect** (carve-crumble path; severing/fatigue contributed zero).
- Model A calibration: per-tap cap 0.03027/tap, α=0.00197456, DFIX=65536 — measured/derived guarantee of no complete disintegration before exactly 1e9 accepted taps.
- Five 30M-scale simulations + 60M distributed continuation within budget; completion/recovery 7/7 PASS + synthetic billion-scale terminal demo.
- Largest natural fragment 14 cells (≥1,000-cell separation honestly unresolved).

Founder decisions D3–D8 remain open (idempotency retention, ray contract, fragment policy, cap margin, visual cadence, grain default) — see `stage-0.3/REPORT.md` §18.

**Key artifact dependency for the research packages:** the authentic initial rock used throughout the Model A′ work was recovered from the Stage 0.3 checkpoint `histories/B_distributed/state_10000.pkl` (on that branch). Preserve that branch.

## 6. The Conserved Material Ledger investigation (review 1)

**Location in this package:** `conserved-material/` (128 KB; scratch source `/tmp/dent-poc/conserved-material/`, mirror `/workspace/conserved-material-poc/` — byte-identical, only `__pycache__` excluded here).

**Report:** `conserved-material/CONSERVATION_ENGINE_INVESTIGATION.md` — an alternatives study vs Model A: exact fixed-point material ledger (M0/Mr/N/q = (M0−Mr)/N), spatially local damage, three representation options (A: Model A + accounting; B: conserved fragments/debris; C: hierarchical), E1–E7 experiments (conservation, threshold handling, invariant, spatial differentiation, surface interaction, efficiency, terminal event), reproducible commands, decision table.

**Important:** this first round contained defects later exposed and quantified by the Model A′ round (`cm_rock.py` has the double per-tap budget and the coarse ray resolver; the E6 comparison had a ~50,000× cap configuration mismatch; the initial rock was a 2.44 % substitute, later replaced by exact recovery). **Read the Model A′ validation (§7) as the superseding authority wherever the two conflict.**

## 7. The Model A′ investigation and its actual findings (review 2)

**Location in this package:** `model-a-prime/` (58 files, ~58 MB; scratch source `/tmp/dent-poc/model-a-prime/`, mirror `/workspace/model-a-prime-poc/` — byte-identical, only `__pycache__` excluded here).

**Report:** `model-a-prime/MODEL_A_PRIME_VALIDATION.md` (14 sections, evidence-classed).

Model A′ = existing Model A sparse-voxel physics **+** thin exact integer ledger with ONE authoritative per-tap budget and pre-commit journal-undo rollback **+** renderer-consistent isosurface ray resolver **+** SQLite durable completion counter. Key findings and figures:

- **Original initial rock recovered exactly** from the Stage 0.3 checkpoint: **151,553 cells, density sum 34,816,588** (M0 = 2,281,739,911,168 dfix; sha256 of `pristine_initial.pkl` recorded); the earlier 2.44 % substitute rock is retired. [measured, `results/f_initial_rock.json`]
- **Ray resolver:** new resolver accepted **3,687/3,687 hits in verdict+position agreement with an independent fine-step reference** (0.05-cell reference; 0 false hits, 0 false misses, 0 sub-ISO hits; 99.837 % within 0.15 cells coarse → **100 % after adjudication**, when all 6 remaining outliers proved to be defects of the coarse reference itself, engine≈10⁻¹⁰ cells error vs the 0.002-cell re-reference). Old resolver on the same 3,856 rays: 43.94 % within 0.15 cells, median 0.30 cells, p99 17.87, max 38.10, 79.1 % of hits on invisible sub-ISO material, 69 false hits, 892 false misses. [measured, `results/a_surface.json`, `a_outlier_adjudication.json`, `a_final_stats.json`]
- **Budget defect reproduced:** the original ledger allowed budget reuse (local carve budget + fresh debris budget in the same tap); **459/6,000 taps exceeded the per-tap allowance (max 1.210×)** while the log-only cumulative checker recorded 0 violations. [measured, `results/b_budget_audit.json`]
- **Shared-budget correction:** with one authoritative per-tap budget, **zero violations in 6,000 taps** (max/q = 1.000, 0 rollbacks needed); adversarial fault injection was detected pre-commit and rolled back byte-identically (state hashes preserved). [measured, same file]
- **Durable completion/recovery prototype: 10/10 tests passed** — 6 subprocess crash points, real SIGKILL mid-transaction, 4-way concurrent final-tap race (exactly 1 winner), duplicate-uuid idempotency, post-completion rejection, no caller-supplied counter injection point, death between completion and publication. SQLite WAL, synchronous=FULL, BEGIN IMMEDIATE; authoritative count = tap-row count. [measured, `results/d_durable.json`, `db/d*.db`]
- **Ledger performance overhead ≈ 30–31 %** on a configuration-matched re-run (Model A 0.349/0.499 ms/tap → ledger 0.454/0.656; ISO resolver adds 0.657/0.813; full-recount verification +0.83 ms/tap validation-only; RSS 74–80.5 MB). The earlier E6 comparison's inconsistency was root-caused (caps differed ~50,000× across engines) and superseded. [measured, `results/e_perf.json`]
- **Connected-visible-rock survival until the billionth tap remains UNPROVEN.** Separately measured: invisible inventory ≤ 0.91 % through 8,000 compressed-lifetime taps; **visually (6-connectivity) the rock remained ONE connected object in all tested damaged states** (bond-graph "74k fragments" were artifacts); sub-ISO pressure inside the main component reached 31.9 % at 8,000 taps. The ledger is a mass guarantee only — the design still lacks a first-class *connected visible main-object reserve* invariant. [measured subset / unknown beyond]
- **Hierarchical-DDA block skipping measured slower** (0.775×) in Python at ~152k-cell scale with 0 contact mismatches — Option C block-skipping doesn't pay at this scale in Python.
- **Determinism proven at reduced scale:** two identical 1,500-tap pipeline runs produced identical state hashes (`354bdb0b…`). [measured, `results/det_check.json`]

**No billion-tap physical simulation was run or claimed.** Largest physical runs: 8,000 compressed-lifetime taps (α≈98.7) and 5,000 billion-α cost-benchmark taps; durable tests used N=10 fixtures. The compressed-α recipe (alpha = q_legacy/15.33) measures cost and failure modes, not billion-scale evolution.

## 8. Proven vs experimental vs unresolved

**Proven at measured scale** [measured]: exact integer ledger conservation under one budget; pre-commit rollback; renderer-consistent ray resolution on 3,856 rays / 5 families vs independent reference; miss rejection with zero redirection; SQLite completion/recovery/idempotency at fixture scale; configuration-matched performance deltas; determinism hash-equality at 1,500 taps.

**Experimental (directionally reliable, not product guarantees):** fragment-kill behaviour; bond-vs-visual partition analysis (3 damaged states); sub-ISO/invisible fractions through 8,000 compressed taps; hier-DDA cost comparison; compressed-α ledger overhead ratios.

**Unresolved (blockers):**
1. Visible/hittable/connected survival guarantee to exactly tap 10⁹ — no invariant exists yet; ledger positivity ≠ visual survival (§7 above).
2. Fragment/debris/fines rendering and hittability policy — debris and fines are ledger entries only in the POC; deliberately left as an open product decision.
3. Completion store at production scale (N=10 fixtures only; billion-scale row sizing/load untested).
4. Salting production-engine validation overhead into the 30 % figure (batching amortisation not modelled).
5. Long-horizon geometric behaviour near tap 10⁹ at real tap rates — nothing measured.
6. Fragment convergence (≥1,000-cell natural fragment separation) — unresolved since Stage 0.3.
7. `s01_c.py` voxelizer source provenance — the initial rock was recovered **exactly from its output checkpoint**, not from source code on the evidence branch [unknown].

## 9. Outstanding physical-engine and architecture blockers (priority order)

1. **Design + prove the connected-visible reserve invariant** (extend M(n) ≥ M(n−1) − q with a first-class connected-visible-main-object floor checked pre-commit). Without it, Dent cannot truthfully promise requirement 10.
2. **Decide fragment/debris/fines rendering + hittability policy** (options and consequences quantified in the Model A′ report §6).
3. **Define the canonical surface contract** (resolver ↔ renderer ↔ collision must share the DENS_ISO trilinear definition; parity fixtures from Stage 0.3 are the starting point).
4. **Scale the completion store** to production sizing/concurrency and decide its relationship to the existing merged Rails-ceiling logic in `backend/main.py` (the current backend ceiling and the SQLite prototype both enforce the 10⁹ limit — a single authoritative mechanism must be chosen).
5. **Performance engineering** for the ledger (~30 % Python overhead) or accept it; resolve fragment-graph memory at real scale.
6. **Multi-day real-rate simulation** before any appearance claims near tap 10⁹.

**Recommended next investigation:** blocker 1 — the connected-visible reserve invariant, on the authentic rock, at compressed-α first, then a real-rate short horizon. It is the single unproven item that blocks an honest product promise; everything else is engineering scale-up.

## 10. Explicit restrictions on changes (carry forward)

- **Do not modify the Dent application**, `backend/`, `app/`, or the existing Git working tree / production branch.
- **Do not commit, push, create branches, open/merge PRs** for this research (PR #10 must remain unmerged; do not update it).
- **Do not deploy anything**; **do not touch the production Railway database** or anything that creates/changes production taps or records.
- All physical-engine work stays in isolated scratch/POC directories until the founder explicitly authorises implementation.
- Do not claim: a billion-tap physical simulation, mass-ledger-equals-geometry guarantees, unproven crash-durability, or hit accuracy beyond measured references.
- Accepted vs rejected taps remains an absolute distinction; never redirect rejected rays (no snap-to-nearest, no old-hit reuse).

## 11. Package contents and verification

```
research/
├── handover/
│   ├── DENT_CURSOR_HANDOVER.md        ← this document
│   └── MANIFEST.md                    ← per-file path, size, purpose, SHA-256
├── model-a-prime/                     ← Model A′ validation evidence (58 files, ~58 MB)
│   ├── MODEL_A_PRIME_VALIDATION.md    ← the authoritative Model A′ report
│   ├── results/  (12 JSONs: a_surface, a_outlier_adjudication, a_final_stats,
│   │              b_budget_audit, c_geometry, c_visual_partition, d_durable,
│   │              e_perf, e_hier_dda, det_check, f_initial_rock, smoke_test)
│   ├── src/      (maprim_rock.py engine, modelA_stage03.py, cm_rock.py, store.py,
│   │              worker.py, streams.py, common.py, s01_c.py, experiment scripts,
│   │              recover_initial_rock.py, pristine_initial.pkl)
│   ├── db/       (11 SQLite fixture DBs from crash tests — synthetic, N=10)
│   ├── renders/  (damaged-state pickles + summaries)
│   └── logs/
└── conserved-material/                ← Conserved Material Ledger evidence (28 files)
    ├── CONSERVATION_ENGINE_INVESTIGATION.md
    ├── src engines (cm_rock.py, modelA_stage03.py, common.py, s01_c.py, streams.py)
    ├── exp1–exp7 scripts, probe_hash.py
    ├── results/ (E1–E7 JSONs incl. e5b isosurface agreement, e5c grazing)
    └── logs/
```

The original Stage 0.3 evidence remains under `stage-0.3/` on this branch, exactly as delivered by PR #10 — it is not duplicated here (the research trees reference its checkpoints, e.g. Part F's rock recovery reads `stage-0.3/histories/B_distributed/state_10000.pkl`).

Duplication note: both research trees existed twice (scratch `/tmp/dent-poc/…` and workspace mirrors). The paired copies were verified **byte-identical** (`diff -rq` clean, excluding `__pycache__`); each is included exactly once here. `__pycache__` bytecode directories were excluded from both trees (regenerable, not evidence) — **the only files omitted**. All files are ordinary Git blobs (largest: 9.5 MB renders) — no Git LFS is used. Note: the branch's shared `.gitignore` contains a global `*.db` rule (backend-artifact ignore); the 11 Part D fixture databases were deliberately force-added because they are crash-test evidence, not runtime artifacts. No credentials, API keys, tokens, passwords, or production database contents are included (text-scanned before archiving; DBs are synthetic N=10 fixtures).

Verification: `MANIFEST.sha256` (standard `sha256sum -c` format, shipped under `research/handover/`) carries a SHA-256 for every transferred file. Re-verify after checkout with:

```bash
cd research && sha256sum --check MANIFEST.sha256
```
