# Phase Model Setup Rescue 4 Report

## Summary

- Replaced the model setup screen copy with a recommendation-first flow.
- Added a single guided setup card with detected runtime, selected/recommended path, status checklist, required-now section, primary CTA, and fallback CTA support.
- Moved compatible model choices behind an `Other options` disclosure; the guided card renders before options even when capture fixtures open alternatives.
- Kept hosted credentials, raw model fields, manual commands, setup logs, and install/test controls in the existing Advanced section.
- Updated layout assertions for the new model setup title.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/index.html`
- `scripts/check_local_ui_layout.mjs`
- `docs/design/screenshots/model-setup-rescue-phase-4-before/`
- `docs/design/screenshots/model-setup-rescue-phase-4-after/`

## Browser Evidence

- Before screenshots: `docs/design/screenshots/model-setup-rescue-phase-4-before/`
- After screenshots: `docs/design/screenshots/model-setup-rescue-phase-4-after/`
- Viewports captured: 390x844, 768x1024, 1024x768, 1366x768, 1440x900, 1920x1080.
- Before evidence showed `Choose and install models` with four visible model choices as the first setup surface.
- After evidence shows `Recommended model setup`, a runtime strip, one selected/recommended path, four checklist items, and required-now copy before the opened options disclosure.

## Tests Run

- `npm test` - passed.
- `npm run build` - passed.
- `npm run ui:layout -- --state workflow-provider,model-setup-trace-all-options,model-setup-no-model-cpu,model-setup-confirm-cache` - passed across six viewports.
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_model_setup_recommendations.py` - passed.
- `git diff --check` - passed.

## Known Limitations

- The committed trace-all screenshot fixture intentionally opens `Other options` and manually selects SAM3 to preserve existing documentation states; the card labels this as a selected path rather than a backend recommendation.
- Run config generation still uses frontend planning logic. Phase 5 will make `modelSetupRecommendation.runConfigMapping` authoritative.
- Renderer-level assertions for required input visibility, hosted opt-in gating, proof states, and recommendation copy are deferred to Phase 6.

## Follow-Up Tasks

- Route `buildRunConfig` and `guidedEnginePlan` through the backend recommendation mapping.
- Add regression tests for the guided card rendering and collapsed options behavior.
- Add final polish actions such as re-scan runtime and improved empty/error states in Phase 7.
