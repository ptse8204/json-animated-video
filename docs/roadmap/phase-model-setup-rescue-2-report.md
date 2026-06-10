---
historical: true
default_context: false
---

# Phase Model Setup Rescue 2 Report

## Summary

- Added `motionjson.model_setup_recommendation.v0.1`.
- Added `model_setup_recommendation_for_goal(...)` for goal-specific, single-path setup recommendations.
- Exposed the default recommendation in `/api/capabilities`.
- Added `GET /api/model-setup/recommendation?goal=...`.
- Recommendation rules now distinguish CUDA hardware with missing runtime, CUDA-ready proof-missing, MPS fallback, CPU/no-model, hosted opt-in, and no-model workflows.

## Changed Files

- `src/motionjson/model_setup_recommendations.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/ui/server.py`
- `tests/test_model_setup_recommendations.py`
- `tests/test_local_ui_api.py`

## Tests Run

- `python3 -m pytest -q tests/test_model_setup_recommendations.py tests/test_runtime_environment.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py` - passed.
- `npm test` - passed.
- `npm run build` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed and included `motionjson.model_setup_recommendation.v0.1`.

## Known Limitations

- The UI still uses hard-coded model setup selection until Phase 3.
- The default `/api/capabilities` recommendation is for `trace_one_object`; goal-specific UI should use the dedicated endpoint or request refreshed capabilities in later phases.
- The contract does not run installs, downloads, or hosted checks. It only reports the next safe action.
- A diff-review scout was not spawned because the available sub-agent tool requires an explicit user request for sub-agents.

## Follow-Up Tasks

- Make frontend state consume backend recommendation instead of static priorities.
- Align run-config generation with `runConfigMapping`.
