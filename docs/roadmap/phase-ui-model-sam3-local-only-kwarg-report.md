# Phase UI-MODEL-SAM3-LOCAL-ONLY-KWARG Report

## Summary

- Fixed the SAM3 Scene Sweep setup regression where Transformers raised `AutoConfig.from_pretrained() got multiple values for keyword argument 'local_files_only'`.
- Removed `local_files_only` from the `pipeline()` call path to avoid colliding with Transformers internals.
- Kept local-cache behavior offline by temporarily setting `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` only around the verified local-cache pipeline construction.
- Updated SAM3 smoke tests to assert no duplicate `local_files_only`/`model_kwargs` are emitted while offline environment flags are active for local cached model directories.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `tests/test_provider_settings.py`

## Tests Run

- `python3 -m pytest -q tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path tests/test_provider_settings.py::test_sam3_smoke_fails_before_pipeline_when_cached_snapshot_has_no_weights tests/test_provider_settings.py::test_sam3_prepare_model_preserves_runtime_failure_status`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam3_providers.py`
- `npm test`
- `npm run build`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

Latest validation results:

- Targeted SAM3 regressions: 3 passed.
- Provider/UI/SAM subset: 113 passed, 1 skipped.
- Frontend tests: 21 passed.
- Full Python suite: 515 passed, 1 skipped.
- CLI help smoke commands and `git diff --check` passed.

## Known Limitations

- This patch fixes the duplicate keyword crash. If a real Colab runtime still blocks inside Transformers pipeline construction after this, the next architecture change should move SAM3 warmup into a killable subprocess.

## Follow-Up Tasks

- Restart the Colab Local UI server with this commit and retry `Prepare local model`.
