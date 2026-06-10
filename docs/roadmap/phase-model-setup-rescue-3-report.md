---
historical: true
default_context: false
---

# Phase Model Setup Rescue 3 Report

## Summary

- Removed the fresh UI state bias toward `sam2-local`.
- Added recommendation-driven model setup selection state with explicit `auto` versus `user_override` modes.
- Cached backend recommendations by goal and refresh them from `GET /api/model-setup/recommendation?goal=...`.
- Updated model setup rendering and config collection to use the backend-selected connection unless the user manually overrides it.
- Added a stale manual override warning when a selected provider differs from the current backend recommendation.
- Cleared provider defaults from UI presets so presets no longer force SAM providers before capability detection.

## Changed Files

- `src/motionjson/ui/static/modules/state_store.js`
- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_modules.mjs`

## Tests Run

- `npm test` - passed.
- `python3 -m pytest -q tests/test_model_setup_recommendations.py tests/test_runtime_environment.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py` - passed.
- `npm run build` - passed.
- `git diff --check` - passed.

## Known Limitations

- `MODEL_CONNECTION_PRIORITY` remains available as a display/fallback ordering when no backend recommendation is cached yet; it is no longer the primary source after recommendations load.
- The run-config builder still derives provider/discovery mappings from frontend planning logic. Phase 5 will make `runConfigMapping` authoritative.
- The manual override warning is covered by state behavior tests now; broader renderer assertions are deferred to the Phase 6 regression coverage pass.
- Browser screenshots were not captured for this phase because the change affects selection state and warning behavior, not the model setup layout/card structure. Phase 4 will capture before/after rendered evidence for the guided card redesign.

## Follow-Up Tasks

- Replace the current model setup UI with a single guided recommendation card.
- Make run-config generation consume `modelSetupRecommendation.runConfigMapping`.
- Add renderer-level regression tests for required fields, hosted opt-in gating, proof state, and stale override copy.
