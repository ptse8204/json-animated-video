# Phase UI First Run Report

## Summary

- Simplified the normal Local UI into one linear first-run path: goal, video, model setup, prepare/run, run monitor, and review/export.
- Removed the duplicate sidebar goal picker from the normal shell and kept the four storyboard goal cards as the primary task choice surface.
- Made Model setup show one recommended compatible model by default, with alternatives behind `Change model` and raw paths, endpoints, API keys, diagnostics, logs, and manual commands inside `Advanced`.
- Added first-run SAM recommendation behavior to the UI config layer: SAM2 prompt tracking for one-object cutout, SAM3 Scene Sweep for everything-in-scene, SAM2 HF automatic masks as the fallback, and SAM3 concept for text search.
- Kept failed/canceled runs inside the guided flow with the existing recovery actions visible from the run monitor path.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_ui_first_run_simplicity.py`
- `docs/design/screenshots/ui-first-run-before/`
- `docs/design/screenshots/ui-first-run-after/`

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `node --check src/motionjson/ui/static/config_builder.js`
- `npm test`
- `npm run lint`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py tests/test_local_ui_api.py`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-first-run-before --state workflow-goal,workflow-video,workflow-provider,workflow-run,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-first-run-after --state workflow-goal,workflow-video,workflow-provider,workflow-run,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `git diff --check`

## Visual Evidence

- Before screenshots: `docs/design/screenshots/ui-first-run-before/`
- After screenshots: `docs/design/screenshots/ui-first-run-after/`
- Captured viewports: `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.
- Captured states: goal, video, model setup, run monitor, and failed-run recovery.

## Known Limitations

- The layout screenshot command still prints a non-fatal Python `resource_tracker` semaphore warning during mock job shutdown.
- Phase 2 validates the simplified UI path and config behavior, but the docs and Colab still need to be updated to present UI-owned model setup as the primary path.
- Full-repository validation is reserved for Phase 3 after documentation updates.

## Follow-Up Tasks

- Update docs and the Colab notebook so manual SAM commands, checkpoint paths, and environment variables are clearly Advanced fallback material.
- Capture final browser evidence for the documentation phase.
- Run full `python3 -m pytest`, CLI help smokes, npm checks, and layout validation before the final phase commit.
