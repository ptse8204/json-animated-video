# Phase UI-MODEL-SAM3-STALL-RECOVERY Report

## Summary

- Inspected the exact Chrome tab reported by the user: `MotionJSON Local UI` on the Colab URL. The active setup job was stuck after `loading_transformers_pipeline` with no later `model_loaded`, `model_device_verified`, or `warmup_started` event.
- Tightened SAM3 Scene Sweep smoke setup so cached local `from_pretrained` directories must include model weight files, not only `config.json`.
- Forced Transformers pipeline construction for recorded local SAM3 cache directories to use `local_files_only=True`, so smoke fails clearly on incomplete snapshots instead of silently attempting more resolution during model load.
- Added UI stall detection for setup jobs. If a prepare/smoke job has no backend event for more than a minute, the progress card switches to warning copy with elapsed time and explicit cancel/log guidance.
- Made provider setup cancellation terminal: a late model-loader result can no longer overwrite a user-canceled setup job.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `tests/test_provider_settings.py`
- `scripts/test_ui_config_builder.mjs`
- `docs/design/screenshots/ui-model-sam3-stall-recovery/`

## Tests Run

- Chrome inspection of the user-selected MotionJSON tab only; active job id `9f33577361f64828bfd657a7f08aaebd` last emitted `loading_transformers_pipeline` at `2026-05-28T07:23:00.398849+00:00`.
- `python3 -m pytest -q tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path tests/test_provider_settings.py::test_sam3_smoke_fails_before_pipeline_when_cached_snapshot_has_no_weights tests/test_provider_settings.py::test_provider_setup_finish_does_not_override_user_canceled_job tests/test_provider_settings.py::test_sam3_prepare_model_preserves_runtime_failure_status`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam3_providers.py`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-sam3-stall-recovery/after --state model-setup-sam3-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

Latest validation results:

- Targeted regressions: 4 passed.
- Provider/UI/SAM subset: 113 passed, 1 skipped.
- Frontend tests: 21 passed.
- Full Python suite: 515 passed, 1 skipped.
- UI layout command passed; Python reported one resource-tracker warning during shutdown after screenshot generation.

## Known Limitations

- The current Colab tab is running code from before this patch. Restarting/reloading the Local UI server in that notebook is required before this recovery behavior appears there.
- This patch prevents incomplete local snapshots and improves stalled-job visibility. It does not make Transformers model construction interruptible inside the already-running Python thread; cancel now remains terminal in the UI/database even if the underlying library call returns later.
- Real CUDA acceptance still needs to be rerun in Colab after deploying this patch.

## Follow-Up Tasks

- Restart the Colab Local UI server with this patch, retry `Prepare local model`, and verify the setup advances past `model_loaded`, `model_device_verified`, and `warmup_succeeded`.
- If Transformers still blocks inside pipeline construction with a complete local snapshot, move SAM3 smoke/warmup into a killable subprocess with streamed progress events.
