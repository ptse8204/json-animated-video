# Phase Model Setup Rescue 6 Report

## Summary

- Added layout-regression checks for the guided model setup card title, selected recommendation title, four-step checklist, required-now copy, no-model CPU copy, and hosted credential placement.
- Updated the Phase 03b provider settings UI test to match the recommendation-driven model setup title.
- Verified the model setup rescue path with targeted browser coverage across the required layout viewports.

## Changed Files

- `scripts/check_local_ui_layout.mjs`
- `tests/test_phase03b_provider_settings_ui.py`

## Tests Run

- `npm run ui:layout -- --state workflow-provider,model-setup-trace-all-options,model-setup-no-model-cpu,model-setup-hosted-warning,model-setup-confirm-cache,model-setup-cache-success` - passed across 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and 1920x1080.
- `npm test` - passed.
- `npm run build` - passed.
- `npm run lint` - passed.
- `python3 -m pytest -q tests/test_runtime_environment.py tests/test_model_setup_recommendations.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py` - passed with 71 tests.
- `npm run ui:layout` - interrupted after more than 13 minutes without output; the matching temp backend and headless Chrome processes were cleaned up.

## Known Limitations

- The full layout sweep did not complete in this run, so Phase 6 relies on the targeted model setup layout matrix plus unit/build/lint coverage.
- The layout assertions verify the guided setup states in mock/no-model mode; GPU/provider installation paths remain capability-gated and covered by backend recommendation tests rather than real ML smoke tests.

## Follow-Up Tasks

- Investigate why the full `npm run ui:layout` sweep can hang on this machine before requiring it as a gate for the broader UI matrix.
- Continue Phase 7 with product copy, accessibility labels, re-scan behavior, and clearer capability-scan failure states.
