---
historical: true
default_context: false
---

# Phase Model Setup Rescue 9 Report

## Summary

- Promoted the SAM3 Hugging Face token from an optional hint to a required normal-path input when Scene Sweep still needs a gated `facebook/sam3` download.
- Changed the trace-all recommendation contract so the normal card returns `status=needs_input` plus `primaryAction.id=save_and_auto_setup` instead of hiding the token and pretending setup can proceed automatically without it.
- Updated local SAM3 guided setup so `prepare_model` verifies Hugging Face access before caching or downloading weights. If the token is missing or invalid, setup stops before download instead of continuing blindly.
- Exposed the saved Hugging Face token state in provider capability metadata so the recommendation endpoint can make the correct guided-field decision.

## Changed Files

- `src/motionjson/capabilities.py`
- `src/motionjson/model_setup_recommendations.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `tests/test_model_setup_recommendations.py`
- `tests/test_provider_settings.py`
- `docs/roadmap/phase-model-setup-rescue-9-report.md`
- `docs/design/screenshots/model-setup-rescue-phase-9-after/`

## Browser Evidence

- Before baseline: `docs/design/screenshots/model-setup-rescue-phase-8-after/`
- After screenshots: `docs/design/screenshots/model-setup-rescue-phase-9-after/`
- Captured states:
  - `workflow-provider`
  - `model-setup-sam3-local`
- Captured viewports:
  - `mobile-390`
  - `tablet-768`
  - `tablet-1024`
  - `laptop-1366`
  - `desktop-1440`
  - `desktop-1920`

## Tests Run

- `python3 -m py_compile src/motionjson/model_setup_recommendations.py src/motionjson/capabilities.py src/motionjson/backend/provider_setup_jobs.py` - passed.
- `python3 -m pytest -q tests/test_model_setup_recommendations.py tests/test_provider_settings.py::test_prepare_model_checks_hugging_face_access_before_sam3_download` - passed with 11 tests.
- `node --test scripts/test_ui_modules.mjs scripts/test_ui_config_builder.mjs` - passed.
- `python3 -m pytest -q tests/test_runtime_environment.py tests/test_model_setup_recommendations.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py tests/test_provider_settings.py::test_prepare_model_records_cache_smokes_and_refreshes_public_settings tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path tests/test_provider_settings.py::test_prepare_model_checks_hugging_face_access_before_sam3_download` - passed with 76 tests.
- `npm test` - passed with 23 tests.
- `npm run build` - passed.
- `npm run lint` - passed.
- `npm run ui:layout -- --state model-setup-sam3-local --viewport mobile-390,desktop-1440` - passed.
- `git diff --check` - passed.

## Known Limitations

- Hosted guided setup still uses the hosted settings test path rather than a frame-level hosted smoke in the normal one-button flow.
- The screenshot runner still has an intermittent Chrome startup flake on some one-off reruns.

## Follow-Up Tasks

- Add a browser-level test that asserts the SAM3 guided card shows the Hugging Face token field before cache when `facebook/sam3` is not already resolved locally.
- Add a focused retry path test for invalid Hugging Face tokens during `prepare_model`.
