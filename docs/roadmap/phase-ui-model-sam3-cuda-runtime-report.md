# Phase UI-MODEL-SAM3-CUDA-RUNTIME Report

## Summary

- Working tree note: this phase continued from the active user-requested implementation state; no unrelated changes were reverted.
- Split the normal SAM3 Scene Sweep cache directory from the advanced official `sam3.pt` checkpoint path in the Local UI.
- Added an explicit Advanced-only local-path endpoint so the UI can show and copy the recorded cached `facebook/sam3` directory without putting that path into editable form payloads, setup logs, run configs, or normal provider settings.
- Replaced SAM3 Scene Sweep "cache means ready" behavior with a backend runtime verification path: resolve cache, verify local files, check CUDA when requested, instantiate the Transformers `mask-generation` pipeline from the resolved path, inspect model device placement, run bounded warmup inference, and persist a safe runtime verification summary.
- Updated guided setup and extraction worker preflight metadata so runs reuse the server-side resolved model/device contract and stream model/GPU/warmup progress without exposing raw paths.
- Updated the model setup UI to show the product flow users care about: Environment, Download, Load on GPU, Warm up, Ready to run.
- Addressed post-implementation review findings: extraction now rejects cache-only SAM3/SAM2 HF runtimes until smoke/warmup verification exists, runtime verification is invalidated when the selected model or device changes, and guided `prepare_model` preserves real runtime failures instead of downgrading them to generic blocked states.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `tests/test_provider_settings.py`
- `tests/test_local_ui_api.py`
- `scripts/test_ui_config_builder.mjs`
- `docs/design/screenshots/ui-model-sam3-cuda-runtime/`

## Tests Run

- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-sam3-cuda-runtime/before --state model-setup-sam3-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-sam3-cuda-runtime/after --state model-setup-sam3-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam2_providers.py tests/test_sam3_providers.py`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

Latest validation results:

- Frontend tests: 21 passed.
- Targeted provider/UI/SAM suite: 132 passed, 1 skipped.
- Full Python suite: 513 passed, 1 skipped.
- CLI help smoke commands and `git diff --check` passed.

## Known Limitations

- The automated test suite uses mocked CUDA/Transformers runtimes. The manual Colab acceptance path still needs to be run on a real CUDA notebook with approved `facebook/sam3` access.
- The explicit Advanced local-path endpoint intentionally returns the cached SAM3 directory for Local UI display only. Normal public provider settings and setup job payloads continue to redact it.

## Follow-Up Tasks

- Run the manual Colab acceptance flow with real `facebook/sam3`: Prepare local model, verify CUDA warmup, run a small Scene Sweep extraction, and confirm candidate review artifacts.
- Consider persisting richer GPU telemetry from long-running extraction jobs when PyTorch exposes stable memory counters.
