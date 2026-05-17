# MotionJSON Repository Status

Baseline recorded: 2026-05-16 21:18 PDT

This status table is a Phase 00 snapshot. It separates what is implemented in
the repository from what is partial or still planned for the public onboarding
roadmap in `docs/codex_future_plan.md`.

## Implemented

| Area | Evidence |
| --- | --- |
| Python package and CLI | `pyproject.toml` declares package `motionjson`, Python `>=3.10`, and console script `motionjson = motionjson.cli:main`. `python3 -m motionjson.cli --help` passes. |
| Core extraction CLI | `extract`, `validate`, `correct`, `export`, `benchmark`, `backend`, and `ui` are top-level CLI commands. |
| CPU/no-model providers | `threshold`, `motion`, `external`, and `mock` providers report ready in `backend diagnostics --json`. |
| Optional provider diagnostics | Diagnostics report unavailable SAM2, hosted segmentation, detector, YOLO, and OpenRouter paths with reasons and install/configuration hints. |
| Local backend | `src/motionjson/backend/` includes SQLite-backed auth, projects, assets, jobs, worker, API keys, support, billing metadata, webhooks, library, and beta workflows. |
| Local UI command | `python3 -m motionjson.cli ui --help` passes and exposes `--mock`, `--no-open`, host, port, db, and storage-root flags. |
| Static UI shell | `npm run build` checks `index.html`, `app.css`, `app.js`, and `config_builder.js` in dependency-free static UI mode. |
| Runtime and SDK packages | Root npm workspace includes `packages/motionjson-runtime` and `packages/motionjson-sdk`; `npm test` passes 19 Node tests. |
| Python tests | `python3 -m pytest -q` passes 228 tests. |
| Benchmark fixture support | `benchmark` CLI exists and tests cover benchmark behavior, including whole-frame regression fixtures. |
| Raster fallback diagnostics | `src/motionjson/track_filters.py` defines reason codes such as `masks_too_large_whole_frame`, and pipeline writes `fallback_diagnostics.json`. |
| Prior implementation reports | `docs/roadmap/phase-0-report.md` through `docs/roadmap/phase-14-report.md` and `docs/roadmap/final-qa-release-report.md` exist. |

## Partially Implemented

| Area | Current state | Gap |
| --- | --- | --- |
| Public README | `README.md` is still a Codex planning packet. `README_old.md` is more user-facing and useful as source material. | Phase 01 must rewrite the root README for first-time users and move planning text into Codex docs. |
| Screenshot and demo assets | No files were found under `docs/assets/`. | Phase 01/03 must define and generate real README screenshots or explicitly marked placeholders in `docs/assets/README_ASSETS.md`. |
| Generated output policy | `out/demo/**` is tracked, and `out/demo_red_ball/` is untracked. `.gitignore` ignores `out/external/` and `out/audit*/`, but not all generated demo output. | Phase 00/09 follow-up should decide which tiny demo outputs remain tracked and which generated artifacts are ignored. |
| Free hosted run paths | Devcontainer, Codespaces, Colab, and Hugging Face Space paths are referenced in the future plan. | Phase 02/10 must verify or add the actual files and docs. |
| Docs information architecture | `docs/index.md` exists but reads like a release documentation list. | Phase 04 should make docs navigable by user intent and add glossary/troubleshooting/examples as needed. |
| Browser screenshots | Prior reports mention manual UI smoke testing. | Future phases need automated screenshot capture and README asset generation. |

## Planned Or Not Bundled By Default

| Area | Status |
| --- | --- |
| Local SAM2 execution | Optional. Diagnostics report `sam2` is not importable and checkpoint/config env vars are unset. |
| Hosted SAM2 execution | Optional. Diagnostics report hosted endpoint/auth env vars are unset and network calls are disabled by default. |
| Text detector discovery | Optional/scaffolded. Diagnostics report `groundingdino` and `TEXT_DETECTOR_MODEL` are unavailable. |
| Known-class detector discovery | Optional/scaffolded. Diagnostics report `ultralytics` and `CLASS_DETECTOR_MODEL` are unavailable. |
| OpenRouter/VLM reasoning | Optional. Diagnostics report `OPENROUTER_API_KEY` is unset and OpenRouter is not a segmentation provider. |
| Production hosted service | Not established by Phase 00. Existing backend/UI are local-first and suitable for local smoke checks. |

## Repo Metadata Recommendations

| Field | Recommendation |
| --- | --- |
| GitHub About description | `Local-first tool for turning selected video objects into reusable JSON-controlled motion layers.` |
| Website | Link to hosted docs or the README once Phase 01/04 are complete. |
| Topics | `motionjson`, `video-editing`, `computer-vision`, `segmentation`, `sam2`, `local-first`, `motion-graphics`, `web-animation`, `python`, `javascript`. |
| Release status | Mark as prototype or release candidate until README screenshots, first-run scripts, and generated artifact policy are complete. |
