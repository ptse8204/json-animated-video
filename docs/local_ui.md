# Local UI

The Local UI is a dependency-light static interface served by the local Python backend. It is current user/developer reference, not a redesign spec.

For redesign work, use `docs/product/ui_redesign_brief.md`. Do not preserve cards, right rails, steppers, dashboards, or current panel layout unless the task explicitly asks for that shape.

## Launch

```bash
python3 -m motionjson.cli ui --no-open --debug-mock
python3 -m motionjson.cli ui --host 127.0.0.1 --port 8766
python3 -m motionjson.cli ui --help
```

Windows PowerShell users can use `py -3 -m motionjson.cli ui --no-open --debug-mock`.

Defaults:

- SQLite DB: `.motionjson/backend.sqlite`
- Storage root: `.motionjson/storage`
- Mock/no-model contributor mode: `--debug-mock`

## Source Paths

- Launcher: `src/motionjson/cli.py`
- UI server: `src/motionjson/ui/server.py`
- Static shell: `src/motionjson/ui/static/index.html`
- UI logic: `src/motionjson/ui/static/app.js`
- Config builder: `src/motionjson/ui/static/config_builder.js`
- Styles: `src/motionjson/ui/static/app.css`
- Selector constants: `src/motionjson/ui/static/ui_selectors.js`
- Layout check: `scripts/check_local_ui_layout.mjs`
- UI JS tests: `scripts/test_ui_config_builder.mjs`, `scripts/test_ui_modules.mjs`, `scripts/test_ui_workflow_matrix.mjs`

## Current Product Flow

The normal local flow is:

1. choose or create a local project;
2. register or upload a source video;
3. choose a tracing goal;
4. check provider/model readiness;
5. prepare and run extraction;
6. review candidates/tracks and failures;
7. export reviewed selected objects.

Raw JSON, logs, artifacts, and advanced provider controls should remain available for technical users without dominating the nontechnical path.
The First Run checklist surfaces local runtime readiness before extraction, and the Run monitor keeps job progress, logs, and generated artifacts visible after a run starts.

## API Route Categories

The UI talks to local API routes for:

- health, deployment readiness, capabilities, diagnostics;
- projects, assets, local browser preview files;
- preferences and provider settings;
- run-config validation and extraction jobs;
- job events, progress, cancellation, artifacts;
- candidate review, selected-object tracking, corrections;
- export workflows, rights/lineage, asset library.

Inspect `src/motionjson/ui/server.py` and `src/motionjson/backend/api.py` for route truth.

## Safety Pointers

- Keep CPU/mock/no-model flows usable.
- Keep heavy ML dependencies optional.
- Keep hosted/network calls opt-in.
- Keep credentials server-side and redacted.
- Show provider failures in diagnostics/logs/UI.
- Validate model-generated plans before extraction.
- Route segmentation/tracking through explicit CV providers.
- Explain raster-only output and vector/object-track failures.

See `docs/codex/SAFETY_INVARIANTS.md` and `docs/security/api_keys.md`.

## Validation

```bash
npm run build
npm test
npm run lint
npm run ui:layout
python3 -m pytest -q tests/test_cli_ui.py tests/test_local_ui_api.py
```
