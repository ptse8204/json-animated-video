---
historical: true
default_context: false
---

# Phase Model Setup Rescue 5 Report

## Summary

- Made `modelSetupRecommendation.runConfigMapping` authoritative for provider/discovery planning when the selected path matches the backend recommendation.
- Preserved explicit manual overrides by skipping recommendation mapping when `modelSetupSelectionMode` is `user_override` and the selected connection differs.
- Applied the same mapping precedence to the standalone `config_builder.js` used by workflow matrix tests.
- Strengthened static config validation so hosted SAM2/SAM3 configs without cost/privacy/network opt-in produce shape errors.
- Fixed a latent SAM2 HF config-builder bug where the app-side discovery builder referenced an out-of-scope `effort` variable.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `scripts/test_ui_config_builder.mjs`
- `scripts/test_ui_workflow_matrix.mjs`
- `tests/fixtures/local_ui_workflow_matrix.v0.1.json`
- `tests/test_phase8_ui_config_builder.py`

## Tests Run

- `npm test` - passed.
- `npm run build` - passed.
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_model_setup_recommendations.py` - passed.
- `python3 -m pytest -q tests/test_phase8_ui_config_builder.py` - passed.
- `git diff --check` - passed.

## Known Limitations

- Renderer-level tests for the guided setup card are still deferred to Phase 6.
- Hosted opt-in is now a static config shape blocker in the frontend builder; backend validation already has deeper provider-specific checks.
- Mapping is applied only when the selected path still matches the backend recommendation, so manual override behavior remains possible and intentionally explicit.

## Follow-Up Tasks

- Add broader regression coverage for renderer output, required inputs, proof states, and hosted gating in Phase 6.
- Run the full layout/browser coverage pass in Phase 6.
