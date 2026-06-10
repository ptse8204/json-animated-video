---
historical: true
default_context: false
---

# Phase UI Model SAM3 Smoke Isolation Report

## Summary

- Traced the stuck Model setup state from the Local UI setup job through `provider_setup_jobs.py`, `provider_settings.py`, and the SAM3 direct loader.
- Identified the actual stall point: `Sam3TrackerModel.from_pretrained(...)` runs inside `_run_with_progress_heartbeat()`, which emitted heartbeats indefinitely but had no terminal deadline while the underlying library call was blocked.
- Added an isolated SAM3 smoke/warmup worker process for normal Local UI setup jobs. The parent process streams progress events, redacts local cached model paths, and terminates the worker on timeout so setup can fail recoverably instead of staying in `Setup running`.
- Kept inline/unit smoke paths available for tests and direct debugging, while the browser now requests isolated SAM3 smoke for `Prepare local model` and `Run smoke test`.

## Changed Files

- `src/motionjson/backend/sam3_smoke_subprocess.py`
  - New parent-side subprocess runner with progress streaming, timeout handling, process termination, and local path redaction.
- `src/motionjson/backend/sam3_smoke_worker.py`
  - New child worker that runs `sam3_scene_sweep_warmup()` and emits newline-delimited JSON progress/result/error messages.
- `src/motionjson/provider_settings.py`
  - SAM3 Scene Sweep smoke can now run through the isolated worker when requested.
  - Added `MOTIONJSON_SAM3_SMOKE_TIMEOUT_SECONDS`, defaulting to 900 seconds.
- `src/motionjson/backend/provider_setup_jobs.py`
  - Non-inline SAM3 setup/smoke defaults to isolated smoke unless explicitly overridden.
- `src/motionjson/ui/static/app.js`
  - Local UI sends `useSubprocessSmoke` for SAM3 prepare/smoke actions and treats worker startup as a load-progress event.
- `tests/test_sam3_smoke_subprocess.py`
  - Added subprocess progress/redaction and timeout/termination coverage.
- `tests/test_provider_settings.py`
  - Added cached-path smoke coverage for the isolated SAM3 path.
- `scripts/test_ui_config_builder.mjs`
  - Added a browser-payload regression assertion for `useSubprocessSmoke`.
- `docs/sam3_local.md`
  - Documented isolated smoke/warmup behavior, timeout configuration, and recovery guidance.

## Tests Run

- `python3 -m py_compile src/motionjson/backend/sam3_smoke_subprocess.py src/motionjson/backend/sam3_smoke_worker.py src/motionjson/provider_settings.py src/motionjson/backend/provider_setup_jobs.py`
- `python3 -m pytest -q tests/test_sam3_smoke_subprocess.py tests/test_provider_settings.py::test_sam3_smoke_can_run_in_isolated_subprocess_from_cached_path tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path`
- `npm test`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam3_providers.py tests/test_sam3_smoke_subprocess.py`
- `npm run build`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`

## Known Limitations

- Real Colab acceptance still requires restarting the deployed Local UI/backend with this commit and retrying `Prepare local model`.
- The setup worker is intentionally a readiness/smoke boundary. Extraction model loading still uses the provider runtime path; if extraction later blocks in the same way, the same isolation pattern should be applied to heavyweight extraction runtime setup.
- Three unrelated `.agents/skills/.../SKILL.md` deletions appeared in the working tree during this phase. They were not part of this change and are intentionally left unstaged.

## Follow-Up Tasks

- Rerun the Colab UI flow and verify the setup either reaches `ready_for_extraction` or fails with the new `SAM3 Scene Sweep warmup timed out` message instead of remaining indefinitely active.
- If real extraction stalls after setup succeeds, isolate the extraction-time SAM3 model load with the same parent/worker process contract.
