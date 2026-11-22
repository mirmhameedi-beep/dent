# DENT — Stage 0.3 experimental artifacts

Read-only evidence bundle for the Stage 0.3 investigation (calibration, natural fracture, one-billion-tap lifespan, exact completion). Experimental only — nothing here is product code and no application file was modified.

- `REPORT.md` — full 18-section Stage 0.3 report (labels: measured / derived / estimate / hypothesis / unknown)
- `scripts/` — all experimental scripts (pure stdlib Python; rerun any of them in scratch to reproduce)
- `results/` — every experiment's raw JSON results incl. `s03_synth_results.json` (synthetic billion-scale terminal demo)
- `logs/` — raw run logs, including preserved invalid-run logs (see `REPORT.md` Appendix C)
- `renders/` — all PNGs: equal-tap history sheets (10k…30M), 60M distributed state, fracture close-ups (FRAG25–100), terminal before/after, near-billion + terminalB
- `histories/` — per-history `metrics.jsonl`, `calib.json`, and resumable mile- stone checkpoints (`state_<accepted>.pkl`) for A/B/C/D/E incl. the 60M distributed run

How to re-verify: see `REPORT.md` — scripts are self-contained; gold N=130 Python↔JS parity and cross-check hashes are documented in the report.
