# Phase UI-MODEL-06 Report - Model Plan To Extraction Run

## Summary

UI-MODEL-06 routes server-side model plans into confirmed extraction jobs. The
Local UI now lets a user generate a fake/local model plan from the selected
goal and plain-language intent, inspect privacy/cost/provider/runtime details,
revalidate the generated `ExtractionRunConfig`, and start extraction only after
manual confirmation.

The backend adds a confirmed enqueue route for completed model runs. It
revalidates the server-held plan, blocks validation errors and provider-policy
blockers, creates the extraction job only after confirmation, attaches the
model plan to the job event log, and then starts the worker when requested.

## Changed Files

- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_local_ui_model_connectors.py`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-model-06-before/`
- `docs/design/screenshots/ui-model-06/`
- `docs/design/screenshots/ui-model-06-docs/`

## Browser Evidence

Before:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-06-before
```

After:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-06
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-06-docs
```

Required viewports covered: 390x844, 768x1024, 1024x768, 1366x768,
1440x900, and 1920x1080.

New UI states covered: `model-plan-preview`, `model-plan-warning`,
`model-plan-confirmation`, `model-plan-queued`, `model-plan-running`, and
`model-plan-succeeded`.

Visual findings:

- Before screenshots showed model setup and run preview, but no server
  model-plan confirmation state.
- After screenshots show a distinct plan confirmation panel with planner,
  discovery, mask provider, tracking mode, privacy, cost, runtime, source, and
  validation status.
- Probe screenshots exposed disabled primary buttons that looked active and a
  too-narrow run monitor beside the plan panel. Both were fixed before the
  final screenshot matrix.
- Diff review found repeat confirmation and stale project/video selection
  risks. The backend confirmation route is now idempotent per model run, and
  it rejects selected project/video values that do not match the server-held
  plan source.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_local_ui_model_connectors.py tests/test_provider_settings.py tests/test_phase03b_provider_settings_ui.py`
- `python3 -m pytest -q tests -k "provider or model or ui"`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-06`
- `python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-06-docs`
- `git diff --check`

## Known Limitations

- The default safe path uses the deterministic fake/local planner. Hosted
  planner execution still requires server-side settings, explicit per-run
  network/cost acknowledgement, and the existing hosted gating.
- Text-detector plans can validate structurally while still being blocked by
  local provider readiness when a real text detector is unavailable.
- The model-run store is process-local; this phase records confirmed plans in
  job events after confirmation, but model-run history itself is not durable.

## Follow-Up Tasks

- UI-MODEL-07 should improve the candidate/review states reached after a
  confirmed model-planned run.
- UI-MODEL-08 should simplify the export handoff from reviewed tracks.
- Later hosted-planner work should add explicit per-run hosted confirmation UI
  before setting `allowNetwork=true`.
