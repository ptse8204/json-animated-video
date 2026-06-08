# Phase Model Setup Rescue 1 Report

## Summary

- Added `motionjson.runtime_environment.v0.2` to `/api/capabilities`.
- Runtime detection now separates accelerator hardware from Python/PyTorch readiness.
- NVIDIA hardware can be detected through `nvidia-smi`, `/proc/driver/nvidia/version`, or environment signals even when torch is missing or CPU-only.
- Legacy `environment.profile` and `gpuModelRecommendation` remain present for compatibility and now include the richer classification.

## Changed Files

- `src/motionjson/capabilities.py`
- `tests/test_runtime_environment.py`
- `tests/test_local_ui_api.py`

## Tests Run

- `python3 -m pytest -q tests/test_runtime_environment.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py` - passed.
- `npm test` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed; local runtime classified as `mps_ready`.
- `git diff --check` - passed.

## Known Limitations

- This phase only adds detection and compatibility payloads. The UI is still not recommendation-driven until later phases.
- AMD ROCm and Intel XPU hardware detection is best-effort via torch/env signals and does not block base installs.
- A diff-review scout was not spawned because the available sub-agent tool requires an explicit user request for sub-agents.

## Follow-Up Tasks

- Add the backend model setup recommendation contract.
- Expose goal-specific recommendation API and matrix tests.
