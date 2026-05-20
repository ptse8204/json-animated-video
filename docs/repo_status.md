# MotionJSON Repository Status

Baseline recorded: 2026-05-20 00:09 PDT

This status table reflects the final public-launch audit after the Phase 11G
Asset Library slice. It separates what is implemented in the repository from
what remains optional, environment-dependent, or future work.

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
| Python tests | `python3 -m pytest -q` passes 306 tests in the OD-00 audit environment. |
| Benchmark fixture support | `benchmark` CLI exists and tests cover benchmark behavior, including whole-frame regression fixtures. |
| Raster fallback diagnostics | `src/motionjson/track_filters.py` defines reason codes such as `masks_too_large_whole_frame`, and pipeline writes `fallback_diagnostics.json`. |
| Public README and docs index | The root README is user-facing, includes no-model quick start commands, real screenshots, provider boundaries, troubleshooting links, and current launch risks. `docs/index.md` links first-run, local UI, runtime, provider, benchmark, release, limitations, and final audit docs. |
| Screenshot and demo assets | Real local mock-UI screenshots and deterministic red-ball preview/GIF assets exist under `docs/assets/`, with regeneration commands in `docs/assets/README_ASSETS.md`. |
| Free and low-install run paths | Codespaces, Colab CLI demo, and Hugging Face Space planning docs exist. The Colab path is a checked-in notebook; Hugging Face remains a documented plan, not a production hosted service. |
| Advanced Phase 11 slices | Text-guided mock discovery, automatic proposal mocks, motion-only discovery, detector class presets, export quality routing, rights lineage warnings, and local Asset Library workflows are implemented with CPU/mock tests and phase reports. |
| Prior implementation reports | `docs/roadmap/phase-0-report.md` through `docs/roadmap/phase-14-report.md` and `docs/roadmap/final-qa-release-report.md` exist. |

## Partially Implemented

| Area | Current state | Gap |
| --- | --- | --- |
| Generated output policy | `out/demo/**` is intentionally tracked as the small runtime/web demo; `.gitignore` ignores new generated `out/*` runs, `.motionjson/`, `output/`, local databases, and env files while allowing the tracked demo exception. | New generated assets should be committed only when they are deterministic, documented, small, and required by tests or public docs. |
| Browser screenshots | `scripts/capture_docs_assets.py` captures README UI screenshots with headless Chrome/Chromium when available. | CI has static shell and docs asset checks; full screenshot refresh remains a local/docs maintenance command. |
| Hosted demos | Codespaces and Colab CLI paths are documented and low-install. Hugging Face Space scope is specified. | No public Space is shipped or operated from this repository snapshot. |
| License and release tag | Release notes, checklist, final QA report, and final audit exist. | No license file or signed release tag exists in this repository snapshot. Do not advertise redistribution rights until that is resolved. |

## Planned Or Not Bundled By Default

| Area | Status |
| --- | --- |
| Local SAM2 execution | Optional. Diagnostics report `sam2` is not importable and checkpoint/config env vars are unset. |
| Hosted SAM2 execution | Optional. Diagnostics report hosted endpoint/auth env vars are unset and network calls are disabled by default. |
| Text detector discovery | Optional/scaffolded. Diagnostics report `groundingdino` and `TEXT_DETECTOR_MODEL` are unavailable. |
| Known-class detector discovery | Optional/scaffolded. Diagnostics report `ultralytics` and `CLASS_DETECTOR_MODEL` are unavailable. |
| OpenRouter/VLM reasoning | Optional. Diagnostics report `OPENROUTER_API_KEY` is unset and OpenRouter is not a segmentation provider. |
| Production hosted service | Not established in this repository snapshot. Existing backend/UI are local-first and suitable for local smoke checks. |

## Repo Metadata Recommendations

| Field | Recommendation |
| --- | --- |
| GitHub About description | `Local-first tool for turning selected video objects into reusable JSON-controlled motion layers.` |
| Website | Link to the README or hosted docs page for the release tag; do not link a public demo until persistence/privacy limits are tested. |
| Topics | `motionjson`, `video-editing`, `computer-vision`, `segmentation`, `sam2`, `local-first`, `motion-graphics`, `web-animation`, `python`, `javascript`. |
| Pinned demo issue/project | Pin a “Try MotionJSON locally in 5 minutes” issue or project item with the no-model UI command, red-ball CLI demo, docs assets, and known limitations. |
| First release tag | Use `v0.1.0-rc1` only after choosing a license, updating package versions if needed, and completing the release checklist. |
| Release status | Mark as release candidate, not production hosted service. Heavy ML and hosted demo paths remain optional. |

## Repo Safeguard Recommendations

- Protect the default branch with a branch rule or ruleset.
- Require CI checks for Python tests, docs link/assets tests, JavaScript
  tests/lint/build, package dry runs, and Docker smoke before release-bound
  merges.
- Enable private vulnerability reporting, secret scanning, and push protection.
- Enable Dependabot alerts and grouped updates for Python, npm, GitHub Actions,
  and Docker manifests.
- Add issue templates for bug reports, provider setup failures, docs fixes, and
  feature requests.
- Require a license file before publishing a reusable release or advertising
  redistribution rights.
- Use signed or protected release tags for release candidates.
