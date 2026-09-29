# gstack methodology mapping

This project was planned and built following the workflow encoded in
[garrytan/gstack](https://github.com/garrytan/gstack) — Garry Tan's skill pack that turns
an AI coding agent into a virtual engineering team. The skills themselves are Claude Code
slash commands; this document maps each one onto what was actually done here.

| gstack skill | Role | How it was applied to VibeShift |
|---|---|---|
| `/office-hours` | YC partner | Reframed "wrap my notebook in an app" into **a self-service acoustic-clustering workbench**: drop the CSV, press one button, watch distributed stages execute, explore the vibe-shift story, export a report-ready notebook. |
| `/plan-ceo-review` | CEO / Founder | Scope decisions: local-file dataset (no upload UI), dual ML engine (Spark primary, pandas fallback so the app works on any machine), all four deliverables (notebook export, run console, track explorer, persistence) kept in v1. |
| `/plan-design-review` | Senior Designer | Spotify-dark design system (near-black surfaces `#0a0d0c`/`#121715`, green accent `#1ed760`), heatmap-first information architecture, stage console as the "live pipeline" centerpiece. |
| `/plan-eng-review` | Eng Manager | Locked the architecture: FastAPI + threaded runner (in-process job registry), engine Protocol with 1:1 stage parity between Spark and pandas, per-run Parquet artifacts, Mongo-with-JSON-fallback persistence, polling status contract. |
| `/devex-review` | DX Reviewer | TTHW minimized: two commands to run, dataset card tells you exactly where to put the file, engine badge explains any fallback in plain language. |
| `/qa` | QA Lead | pytest suite (14 tests) covering the cleaning fixes from the transcript, the engine results contract, the full API lifecycle, track filters, and notebook validity; production build verified. |
| `/review` | Staff Engineer | Found and fixed the done-before-artifacts race that could serve empty track pages to fast pollers. |
| `/document-release` | Doc Engineer | README with architecture diagram, setup, engine matrix, test instructions; this mapping document. |

## Decision principles encoded from gstack

1. **Sell the outcome, not the feature.** The product is "see how music's vibe shifted across
   six decades," not "a REST wrapper around K-Means."
2. **Fallbacks must be loud, not silent.** The engine badge always states which engine ran and
   why; the benchmark is labeled honestly when Spark is unavailable.
3. **Every artifact regenerable from config.** Notebooks and results are derived from the run
   document; nothing is hand-edited.
4. **Ship the report with the product.** For a mini-project, the .ipynb export *is* a feature —
   the app writes the deliverable.
