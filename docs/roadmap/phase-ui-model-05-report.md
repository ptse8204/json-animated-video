---
historical: true
default_context: false
---

# UI-MODEL-05 Phase Report - Model Setup Wizard

## Summary

Added a guided Mode and model setup panel to the Local UI main workspace. The
panel keeps `fake-local-planner` as the first no-network/no-key path, surfaces
hosted OpenAI and OpenRouter planning states in plain language, saves hosted
settings through the existing server-side provider-settings API, and tests model
readiness without making hosted network calls.

The dense right-rail Provider settings panel remains available for advanced
configuration, but users no longer need to discover model setup there first.
Hosted flows show missing-key, hosted cost/privacy, invalid-key, and settings
readiness states without returning raw secrets to the browser.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_phase03b_provider_settings_ui.py`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-model-05-before/`
- `docs/design/screenshots/ui-model-05/`
- `docs/design/screenshots/ui-model-05-docs/`

## Browser Evidence

Before screenshots:

- `docs/design/screenshots/ui-model-05-before/` - 61 screenshots.

After screenshots:

- `docs/design/screenshots/ui-model-05/` - 103 screenshots covering the existing
  layout states plus `model-setup`, `model-setup-local`,
  `model-setup-hosted-warning`, `model-setup-missing`,
  `model-setup-invalid`, and `model-setup-success`, including full-page mobile
  model setup captures.
- `docs/design/screenshots/ui-model-05-docs/` - regenerated docs assets.

Representative reviewed captures:

- `docs/design/screenshots/ui-model-05/laptop-1366-model-setup-hosted-warning.png`
- `docs/design/screenshots/ui-model-05/mobile-390-model-setup-invalid-full.png`
- `docs/design/screenshots/ui-model-05/desktop-1920-model-setup-success.png`
- `docs/design/screenshots/ui-model-05/laptop-1366-first-run.png`

Before/after findings:

- Before, provider/model setup was reachable mainly through the right-rail
  Provider settings list. The first visible rows were local mask providers, and
  hosted planners required scrolling.
- After, the main workflow has a readable Mode and model step immediately after
  the goal cards. The local mock planner is visibly ready with no API key, while
  hosted planners show missing-key and cost/privacy warnings before save/test.
- The first full browser pass found 1366px model cards compressed to about
  220px. The model setup grid now drops columns before cards become too narrow.
- Scout review found the hosted error/result message and setup actions were too
  low in the initial screenshot evidence. The result now appears above the
  hosted form, desktop/laptop hosted fields use a compact three-column layout,
  and mobile model setup states include full-page screenshots.
- The expanded screenshot matrix required better browser cleanup; the layout
  script now closes Chrome targets between states and uses a longer capture
  readiness timeout.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_phase03b_provider_settings_ui.py tests/test_provider_settings.py tests/test_local_ui_model_connectors.py`
- `python3 -m pytest -q tests -k "provider or model or ui"`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-05 --state extraction-wizard,provider-diagnostics --viewport laptop-1366`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-05 --state model-setup-hosted-warning,model-setup-missing,model-setup-invalid,model-setup-success --viewport mobile-390,laptop-1366,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-05`
- `python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-05-docs`
- `git diff --check`

The layout command still prints the known Python `resource_tracker` semaphore
warning at shutdown, but the final layout result returned `status: ok`.

## Known Limitations

- The wizard saves and tests provider readiness; it does not yet start a model
  plan from natural language. UI-MODEL-06 owns plan confirmation and extraction
  job enqueue.
- OpenRouter remains settings-only until a runtime transport is implemented.
- Hosted model runs still require per-run `allowNetwork` and
  `acknowledgeCostPrivacy` confirmation. The setup wizard does not weaken that
  server-side gate.
- Read-only rendering and diff-review scouts reviewed the phase. Their
  material screenshot-evidence finding was addressed before commit; their
  remaining low-risk test recommendation is to add a future interaction test
  that drives the setup save/test/reset buttons with mocked network calls.

## Follow-Up Tasks

- UI-MODEL-06: connect validated model plans to extraction job confirmation.
- Add a dedicated natural-language intent field once model-plan generation is
  integrated into the guided run flow.
- Continue keeping Provider settings available as advanced detail while moving
  default user tasks into the main guided workflow.
