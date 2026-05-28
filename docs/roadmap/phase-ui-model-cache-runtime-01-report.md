# Phase UI-MODEL-CACHE-RUNTIME-01 Report

## Summary

Implemented the one-click local model setup and cached runtime fix for SAM2 HF
automatic masks and SAM3 Scene Sweep. A successful cache job now records the
private `from_pretrained` directory server-side, public responses only show
recorded/redacted status, and later smoke tests and extraction runs resolve the
private cached path automatically.

The Local UI now promotes a single primary setup path: `Prepare local model`,
`Run smoke test`, then `Continue to run`. The guided `prepare_model` setup
action diagnoses runtime setup, blocks with a concrete next action when
packages/access/paths are missing, caches the selected model after confirmation,
records the server-side path, and runs a bounded smoke test after heavy-runtime
confirmation.

## Changed Files

- `src/motionjson/provider_settings.py`
  - Added shared runtime model resolution for local cached providers.
  - Added backend-only runtime model info.
  - Updated diagnose and smoke behavior so SAM2 HF and SAM3 Scene Sweep use the
    private saved cache path.
  - Ignores redacted public placeholders on save so browser round-trips cannot
    corrupt private cached runtime state.
  - Kept public provider settings redacted with safe cache fields only.
- `src/motionjson/backend/provider_setup_jobs.py`
  - Added `prepare_model`.
  - Added guided prepare progress, runtime blockers, cache recording, and smoke
    orchestration.
  - Ensured setup job results/events are redacted.
- `src/motionjson/backend/worker.py`
  - Injects cached server-side `sam2HfModel` / `sam3TrackerModel` into provider
    backends without putting raw paths into run config artifacts.
- `src/motionjson/ui/server.py`
  - Routes legacy SAM2 HF smoke as local heavy-runtime smoke.
  - Returns refreshed redacted provider settings with setup job start/poll
    responses.
- `src/motionjson/ui/static/app.js`
  - Exposes the primary model setup CTA.
  - Adds `prepare_model` UI handling, refreshed provider settings after setup
    jobs, cache-to-smoke state, and `Continue to run` wording.
  - Stops redacted cached paths from being emitted as editable `customModelId`
    or cache model payload values.
- `scripts/test_ui_config_builder.mjs`
  - Updated model setup state expectations for prepare/smoke/run CTAs.
- `tests/test_provider_settings.py`
  - Added cache-to-smoke, guided prepare, legacy smoke, redaction, and worker
    runtime-injection coverage.
  - Added regression coverage for redacted cached path round-trips preserving
    `runtime_model_source == "saved_cache"`.
- `docs/local_ui.md`
  - Documented guided setup, server-side cached path handling, redaction, and
    SAM3 Scene Sweep versus advanced `sam3.pt` checkpoint separation.
- `docs/design/screenshots/ui-model-cache-runtime-01/`
  - Added before/after rendered evidence for affected Model setup states.

## Tests Run

- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam2_providers.py tests/test_sam3_providers.py`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

Final results:

- `npm test`: 21 passed.
- `npm run build`: ok.
- Targeted backend suite: 127 passed, 1 skipped.
- Full Python suite: 508 passed, 1 skipped.
- CLI help commands: ok.
- `git diff --check`: ok.

## Browser Evidence

Captured before and after screenshots across the six required viewports:

- `mobile-390`
- `tablet-768`
- `tablet-1024`
- `laptop-1366`
- `desktop-1440`
- `desktop-1920`

Captured states:

- `model-setup`
- `model-setup-sam3-local`
- `model-setup-confirm-cache`
- `model-setup-cache-success`
- `model-setup-sam3-missing-runtime`

Evidence path:

- `docs/design/screenshots/ui-model-cache-runtime-01/before/`
- `docs/design/screenshots/ui-model-cache-runtime-01/after/`

The layout command returned `status: ok` for both before and after runs. The
mock capture helper emitted a Python `resource_tracker` shutdown warning about
one leaked semaphore in both runs; the browser layout validation still exited
successfully.

## Review

Read-only `diff-review-scout` found one blocker before commit: a cached local
model directory could be rendered as `[LOCAL_PATH_REDACTED]` in a browser form
and then be submitted back as `customModelId`, invalidating the private saved
cache. The blocker was fixed before handoff by:

- omitting redacted/empty `customModelId` in UI setup/provider payloads;
- ignoring redacted public placeholders in backend provider-settings saves;
- hiding private cached local model paths from public editable custom model
  fields;
- adding a regression that caches a local `from_pretrained` directory, submits a
  redacted `customModelId`, and verifies smoke still uses the private saved
  cache path.

## Known Limitations

- `prepare_model` does not install packages silently. If runtime packages,
  checkpoint/config paths, or device selection are missing, it blocks and
  returns the next action instead of mutating the environment without the user.
- SAM3 official concept/exemplar workflows still require a real local
  `sam3.pt` checkpoint through the advanced `sam3ModelPath` /
  `SAM3_LOCAL_MODEL` path. The normal `facebook/sam3` Scene Sweep cache is not
  copied into that field.
- CPU-only environments still need CPU-safe/no-model workflows or an explicit
  heavy local setup choice. SAM3 Scene Sweep remains CUDA-oriented.

## Follow-Up Tasks

- Add persistent smoke-test recency metadata if the product needs to distinguish
  "cache ready" from "smoked in this UI session" after a browser reload.
- Consider improving the layout capture helper shutdown so the Python
  `resource_tracker` warning does not appear after successful screenshot runs.
