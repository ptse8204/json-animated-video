---
historical: true
default_context: false
---

# Phase Model Setup Rescue 7 Report

## Summary

- Added a normal-mode `Re-scan runtime` action that refreshes capabilities, provider settings, and the backend model setup recommendation.
- Added a runtime scan failure state with plain-language recovery copy, a retry CTA, and Advanced-only manual setup access.
- Improved setup status copy for install, model cache, proof, credential, hosted opt-in, ready, and no-model fallback states.
- Added accessibility labels for setup status chips, runtime badges, checklist items, disclosures, model options, primary CTAs, confirmations, and advanced actions.
- Moved the explicit `Use this anyway` manual override confirmation into the Advanced disclosure only.
- Kept non-model workflows out of the model setup step and clarified the skipped-state copy.
- Replaced model setup stripe accents with full-border state styling on the guided card, progress/status cards, and confirmation cards.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_modules.mjs`
- `docs/design/screenshots/model-setup-rescue-phase-7-before/`
- `docs/design/screenshots/model-setup-rescue-phase-7-after/`

## Browser Evidence

- In-app browser inspection verified the no-model CPU setup card before and after the change. The in-app browser screenshot command timed out, so committed screenshots were captured with the repository layout tool.
- Before screenshots: `docs/design/screenshots/model-setup-rescue-phase-7-before/` with 20 files across the required viewports for `workflow-provider`, `model-setup-no-model-cpu`, and `model-setup-hosted-warning`.
- After screenshots: `docs/design/screenshots/model-setup-rescue-phase-7-after/` with 34 files across the required viewports for `workflow-provider`, `model-setup-no-model-cpu`, `model-setup-hosted-warning`, `model-setup-capability-error`, and `model-setup-advanced-local-sam3`.

## Tests Run

- `node --check src/motionjson/ui/static/app.js` - passed.
- `node --check scripts/check_local_ui_layout.mjs` - passed.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/model-setup-rescue-phase-7-before --state workflow-provider,model-setup-no-model-cpu,model-setup-hosted-warning` - passed across 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and 1920x1080.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/model-setup-rescue-phase-7-after --state model-setup-advanced-local-sam3 --viewport desktop-1920` - passed.
- `npm run ui:layout -- --state model-setup-capability-error --viewport mobile-390` - passed.
- `npm run ui:layout -- --state model-setup-no-model-cpu --viewport desktop-1440` - passed.
- `npm run ui:layout -- --state model-setup-advanced-local-sam3 --viewport desktop-1920` - passed.
- `npm test` - passed with 23 tests.
- `npm run build` - passed.
- `npm run lint` - passed.
- `python3 -m pytest -q tests/test_runtime_environment.py tests/test_model_setup_recommendations.py tests/test_local_ui_api.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py` - passed with 71 tests.
- `git diff --check` - passed.

## Known Limitations

- Multi-state after-layout runs generated the expected screenshots, but twice lost the terminal JSON result after child processes had exited. Focused single-state layout checks were used for explicit pass/fail validation of the new assertions.
- The re-scan action refreshes existing local diagnostics and recommendation endpoints; it does not install dependencies, download models, or call hosted providers.
- In-app browser screenshots timed out, so committed browser evidence comes from the repository headless layout tool.

## Follow-Up Tasks

- Investigate the intermittent PTY/result loss in longer `npm run ui:layout` batches.
- Add an end-to-end browser test for clicking `Re-scan runtime` once the UI test harness has stable long-running browser sessions.
