# UI-SETUP-PROGRESS-01 Report

## Summary

- Hardened Model setup confirmations so confirmed setup actions submit the captured provider id, action, selected model, flags, and unsaved settings from the confirmation snapshot rather than rereading password fields after a re-render.
- Normalized Model setup state decisions so active jobs map to cancel/watch, access failures map back to Hugging Face access checks, cache failures map back to cache/access recovery, missing runtime maps to install, and ready states advance to Prepare.
- Added redacted setup-job progress metadata for cache jobs and other setup actions, with queued/started/cache milestone events and top-level `setupJob.progress`.
- Added a normal-mode setup progress block for install/access/cache/smoke/diagnose jobs while keeping detailed logs in Advanced.

## Changed Files

- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `tests/test_provider_settings.py`
- `docs/design/screenshots/ui-setup-progress-01-before/`
- `docs/design/screenshots/ui-setup-progress-01/`

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `npm test`
- `npm run build`
- `python3 -m pytest tests/test_provider_settings.py tests/test_local_ui_api.py -q`
- `npm run ui:layout -- --state model-setup-sam3-local,model-setup-confirm-access,model-setup-confirm-cache,model-setup-cache-running,model-setup-cache-failed,model-setup-cache-success --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-setup-progress-01`
- `git diff --check`

## Review

- Ran one read-only `motionjson_reviewer` scout before commit.
- Scout found an active `check_access` precedence issue where a running access job could inherit `needs_access` and show the wrong CTA, plus an exceptional-path token snapshot cleanup risk.
- Both findings were fixed before final validation: active access jobs now map to the running/checking state and `Cancel setup`, and confirmation snapshots are cleared if the confirmed setup button is unavailable after render.

## Browser Evidence

- Before screenshots: `docs/design/screenshots/ui-setup-progress-01-before/` with 21 files for the pre-existing setup capture states: `model-setup-sam3-local`, `model-setup-confirm-cache`, and `model-setup-success`.
- After screenshots: `docs/design/screenshots/ui-setup-progress-01/` with 42 files for the requested states: `model-setup-sam3-local`, `model-setup-confirm-access`, `model-setup-confirm-cache`, `model-setup-cache-running`, `model-setup-cache-failed`, and `model-setup-cache-success`.
- Viewports checked: `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.

Exact before screenshots for `model-setup-confirm-access`, `model-setup-cache-running`, `model-setup-cache-failed`, and `model-setup-cache-success` were not available because those deterministic capture states did not exist before this phase. The after matrix adds and validates those states.

## Known Limitations

- The layout capture command still prints the existing Python `resource_tracker` leaked semaphore warning at process shutdown. The layout assertions and screenshot output completed successfully.
- Setup progress is milestone-based. Hugging Face snapshot downloads expose clear labels and indeterminate progress when byte-level progress is not available.

## Follow-Up Tasks

- Add byte-level Hugging Face download progress if the runtime later adopts a downloader hook that can report stable totals without exposing signed URLs or local cache paths.
- Consider moving the sticky mobile workflow footer out of the main viewport capture path if future mobile screenshots need to show every lower setup card without scrolling.
