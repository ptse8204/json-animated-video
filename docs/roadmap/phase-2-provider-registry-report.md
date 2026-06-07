# Phase 2 Report: Provider And Workflow Registry

## Summary

Added a canonical static provider/workflow registry in `src/motionjson/provider_registry.py` with provider IDs, capability IDs, UI connection aliases, workflow support, worker eligibility, setup metadata, validation policy, hosted opt-in requirements, and public-safe serialization.

The Local UI now exposes `/api/provider-registry`, lists it in health/API route metadata, and loads it during root initialization with the existing static UI constants left as fallback behavior. Backend extraction policy now derives allowed/rejected provider sets from the registry.

Provider settings now attach registry summaries to catalog/settings responses and normalize compatible provider aliases before reading or writing settings. Hosted connection aliases such as `sam3-hosted:fal-sam3-image` preserve the selected hosted profile while storing settings under the canonical provider ID.

Drift tests now fail if provider settings, capability diagnostics, worker policy, UI model connections, config-builder presets, or the Phase 1 workflow matrix reference provider IDs that are absent from the registry.

A read-only plan-risk scout reviewed the design before implementation. A read-only diff-review scout found two blocking issues before commit: hosted connection aliases were not yet honored by provider settings test/diagnose routes, and the `sam3-auto-masks` registry entry conflicted with the existing provider-settings catalog implementation flag. Both were fixed and covered by targeted tests before commit.

## Changed Files

- `src/motionjson/provider_registry.py`
- `src/motionjson/backend/models.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_provider_registry.py`
- `docs/roadmap/phase-2-provider-registry-report.md`

## Tests Run

- `python3 -m pytest tests/test_provider_registry.py -q`
- `python3 -m pytest tests/test_provider_registry.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_model_connectors.py tests/test_local_ui_model_connectors.py tests/test_local_ui_workflow_matrix.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py -q`
- `npm test`
- `npm run build`
- `npm run lint`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- Existing `PROVIDER_DEFINITIONS`, capability construction, and UI model-connection constants remain in place for compatibility. Phase 2 makes drift detectable and routes backend policy/API through the registry, but it does not complete a large refactor to generate every old constant from the registry.
- `/api/provider-registry` is static public-safe metadata. Runtime readiness, saved settings, and diagnostics remain on `/api/provider-settings` and `/api/capabilities`.
- `sam3-auto-masks` remains a provider-settings catalog placeholder while `sam3-local` is the runnable Scene Sweep connection and `sam3-auto-masks` is the capability that gates that workflow.
- Browser screenshot evidence was not captured because this phase did not change Local UI layout, cards, panels, fonts, or responsive behavior.

## Follow-Up Tasks

- Gradually derive `PROVIDER_DEFINITIONS`, capability records, and UI connection lists from registry metadata once the drift tests are stable.
- Use registry workflow support to simplify `guidedEnginePlan` and model setup ordering in a later UI modularization phase.
- Extend registry runtime-proof fields when Phase 5 adds concrete proof artifacts and runtime assertions.
