# UI-WORKFLOW-11 Phase Report - Streamline Guided Run And Review Workflow

## Summary

This phase tightens the Local UI around the actual user path instead of the old
details-rail workflow. The first screen now promotes a faster `Pick objects
from one frame` goal, the run monitor shows inline live output previews and
terminal-style logs, and candidate review plus correction controls are moved
back into the main review surface. The backend also adds optional lightweight
automatic object naming for generic placeholder labels and checkpoints object
artifacts during extraction so the UI can surface masks and cutouts while a run
is still active.

## Starting State

The worktree was not clean before this phase. Unrelated existing changes were
present in:

- `.gitignore`
- `docs/design/screenshots/model-setup-rescue-before/`

Those files were left alone.

## Changed Files

- `codex_tasks.yaml`
- `docs/design/local-ui-audit.md`
- `docs/local_ui.md`
- `docs/roadmap/phase-ui-workflow-11-report.md`
- `docs/roadmap/ui_model_connector_plan.md`
- `pyproject.toml`
- `scripts/test_ui_config_builder.mjs`
- `scripts/test_ui_modules.mjs`
- `src/motionjson/image_classifier.py`
- `src/motionjson/model_setup_recommendations.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/modules/provider_connections.js`
- `tests/test_image_classifier.py`
- `tests/test_model_setup_recommendations.py`
- `tests/test_ui_first_run_simplicity.py`

Browser evidence directories generated during the phase:

- `docs/design/screenshots/ui-workflow-11-focus-before/`
- `docs/design/screenshots/ui-workflow-11-focus/`

## Browser Evidence

Focused before captures:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-workflow-11-focus-before --state first-run,model-setup-sam3-local,workflow-run,candidate-review,correction-tools,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920
```

Focused after captures:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-workflow-11-focus --state first-run,model-setup-sam3-local,workflow-run,candidate-review,correction-tools,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920
```

Manual in-app browser checks also verified the live first-run shell before and
after the layout rescue.

Representative captures reviewed during implementation:

- `docs/design/screenshots/ui-workflow-11-focus-before/desktop-1440-first-run.png`
- `docs/design/screenshots/ui-workflow-11-focus-before/laptop-1366-workflow-export.png`
- `docs/design/screenshots/ui-workflow-11-focus/mobile-390-model-setup-sam3-local-full.png`
- `docs/design/screenshots/ui-workflow-11-focus/laptop-1366-first-run.png`
- `docs/design/screenshots/ui-workflow-11-focus/desktop-1440-workflow-run.png`

Findings addressed:

- The default goal picker still pushed users toward broad scene sweep too early.
  The default card set now favors a one-frame object pick path and moves the
  noisier `Find everything in scene` flow under Advanced tasks.
- Run monitor relied too heavily on logs and artifact browsing. It now shows
  inline live previews from registered candidate previews, masks, and cutouts.
- Candidate review, correction state, and correction history were split between
  the main review surface and the right rail. Those controls now live inline in
  the main review workflow.
- The old advanced parameter toolbar repeated status that was already visible in
  the guided summary. It is reduced to a light inline auto-tuning summary plus
  reset action.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_image_classifier.py tests/test_model_setup_recommendations.py tests/test_ui_first_run_simplicity.py`
- `python3 -m pytest -q tests/test_local_ui_api.py -k "review or export or provider"`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `git diff --check`

## Known Limitations

- Automatic naming is intentionally conservative. It only replaces generic
  placeholder labels when the optional `classifier` extra is installed and the
  model maps cleanly to a supported friendly class.
- The lightweight classifier currently covers a curated set of familiar object
  names rather than arbitrary open-vocabulary labels.
- Live run previews depend on candidate or object artifacts being registered by
  the worker. The UI does not expose raw in-memory model state that has not yet
  been written to artifacts.
- The screenshot evidence for this phase is a focused matrix over the screens
  changed here rather than the entire legacy layout-state catalog.

## Follow-Up Tasks

- Extend the focused screenshot matrix to include desktop candidate-review,
  correction, and export captures if the layout harness runtime budget allows.
- Surface classifier prediction provenance more explicitly in the review UI when
  users want to keep or override an automatic name.
- Consider a provider-backed selected-tracking path that avoids precomputing
  full candidate mask sequences for the one-frame object-pick workflow.
