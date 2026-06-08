# Phase Model Setup Rescue 8 Report

## Summary

- Replaced recommendation primary actions that exposed internal setup substeps with a one-button contract: `auto_setup`, `save_and_auto_setup`, `use_fallback`, `retry_setup`, and `continue`.
- Made backend recommendation selection authoritative for the active model path and removed silent frontend fallback to static priority ordering when a recommendation is unavailable.
- Changed the normal model setup card to show one visible primary CTA, inline only the required fields for the recommended path, and keep alternate providers, logs, proof/cache detail, re-scan, and manual actions inside the collapsed Advanced panel.
- Reused the existing local `prepare_model` backend orchestration for the guided setup path so one confirmation can cover diagnose, cache/download, and smoke/proof where supported.
- Added regression coverage for the new recommendation semantics and for the single-CTA setup screen contract.

## Changed Files

- `src/motionjson/model_setup_recommendations.py`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `scripts/test_ui_modules.mjs`
- `tests/test_model_setup_recommendations.py`
- `docs/design/screenshots/model-setup-rescue-phase-8-after/`

## Browser Evidence

- Before baseline for this phase: `docs/design/screenshots/model-setup-rescue-phase-7-after/` from the committed pre-change UI.
- After screenshots: `docs/design/screenshots/model-setup-rescue-phase-8-after/` with 34 files across the required viewports for:
  - `workflow-provider`
  - `model-setup-no-model-cpu`
  - `model-setup-hosted-warning`
  - `model-setup-capability-error`
  - `model-setup-advanced-local-sam3`
- The mock UI was also opened in the in-app browser against `http://127.0.0.1:8765/` to verify the final local server state before screenshot capture.

## Tests Run

- `node --check src/motionjson/ui/static/app.js` - passed.
- `node --check scripts/check_local_ui_layout.mjs` - passed.
- `python3 -m py_compile src/motionjson/model_setup_recommendations.py` - passed.
- `python3 -m pytest -q tests/test_model_setup_recommendations.py` - passed with 9 tests.
- `node --test scripts/test_ui_modules.mjs scripts/test_ui_config_builder.mjs` - passed.
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py` - passed with 57 tests.
- `npm run ui:layout -- --state workflow-provider,model-setup-no-model-cpu,model-setup-hosted-warning,model-setup-capability-error,model-setup-advanced-local-sam3 --viewport mobile-390,desktop-1440` - passed.
- `npm test` - passed with 23 tests.
- `npm run build` - passed.
- `npm run lint` - passed.
- `python3 -m pytest -q tests/test_runtime_environment.py tests/test_model_setup_recommendations.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py tests/test_provider_settings.py::test_prepare_model_records_cache_smokes_and_refreshes_public_settings tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path` - passed with 74 tests.
- `git diff --check` - passed.

## Known Limitations

- The explicit advanced local SAM3 override still uses a manual expert path; it is collapsed under Advanced and is not treated as the normal guided setup flow.
- Longer `npm run ui:layout` screenshot batches still intermittently lose their terminal JSON result after files are written. Focused reruns were used to complete the screenshot set.
- Hosted guided setup currently saves fields and runs the existing hosted settings test path; it does not attempt a hosted frame-level smoke during the normal one-button flow.

## Follow-Up Tasks

- Add a dedicated end-to-end UI test that clicks the guided setup CTA and verifies the automatic transition from `auto_setup` or `save_and_auto_setup` to `continue`.
- Investigate the intermittent PTY/result loss in longer layout screenshot batches.
