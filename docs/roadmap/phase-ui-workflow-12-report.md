# UI-WORKFLOW-12 Phase Report - Finish Keyframe-First Tracking Workflow

## Summary

UI-WORKFLOW-12 finishes the fast keyframe-first workflow so it no longer
behaves like scene sweep. The scan job now stops after one-frame candidate
artifacts, the `track-selected` route can enqueue a child selected-only
tracking job, and the main UI exposes a real `Scan -> Select -> Track` flow.
The shell was also tightened toward a compact editor, model setup now shows a
separate access stage for gated local SAM3 paths, and automatic object naming
switched from a Hub-backed classifier prototype to no-token `torchvision`
MobileNetV3 small weights. The remaining visible entry points back into the old
side-rail workflow are now hidden, with support surfaces mounted inline in the
main workspace instead.

## Starting State

The worktree was not clean before this phase. Unrelated existing changes were
already present in:

- `.gitignore`
- `docs/design/screenshots/model-setup-rescue-before/`

Those files were left untouched.

## Changed Files

- `codex_tasks.yaml`
- `docs/design/local-ui-audit.md`
- `docs/roadmap/phase-ui-workflow-12-report.md`
- `docs/roadmap/ui_model_connector_plan.md`
- `pyproject.toml`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `scripts/test_ui_modules.mjs`
- `src/motionjson/backend/jobs.py`
- `src/motionjson/backend/selected_tracking.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/candidate_review.py`
- `src/motionjson/image_classifier.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/pipeline_adapters.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/modules/state_store.js`
- `src/motionjson/ui/static/modules/workflow.js`
- `src/motionjson/vectorize.py`
- `tests/test_fast_keyframe_workflow.py`

Focused browser evidence directories:

- `docs/design/screenshots/ui-workflow-12-before/`
- `docs/design/screenshots/ui-workflow-12/`

## Browser Evidence

Before:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-workflow-12-before --state first-run,model-setup-sam3-local,workflow-run --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920
```

After:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-workflow-12 --state first-run,model-setup-sam3-local,workflow-run --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920
```

Representative captures:

- `docs/design/screenshots/ui-workflow-12/desktop-1440-first-run.png`
- `docs/design/screenshots/ui-workflow-12/laptop-1366-model-setup-sam3-local.png`
- `docs/design/screenshots/ui-workflow-12/mobile-390-workflow-run.png`

Manual in-app browser verification additionally confirmed:

- the fast goal renders a visible 7-step flow with `Scan`, `Select`, and
  `Track`;
- the compact first-run shell stays nonblank and readable;
- the fast goal’s model-setup screen resolves to a concrete recommendation
  instead of the stale “recommendation unavailable” fallback copy.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_fast_keyframe_workflow.py`
- `python3 -m pytest -q tests/test_image_classifier.py tests/test_model_setup_recommendations.py tests/test_ui_first_run_simplicity.py`
- `python3 -m pytest -q tests/test_local_ui_api.py -k "track_selected or export or provider or preview_file_route_serves_imported_result_directories or keyframe_scan"`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `git diff --check`

## Known Limitations

- The broader GPU work in this phase is focused on the raster/post-mask path
  and GPU-assisted template-match fallback. Candidate filtering itself still
  relies mostly on CPU logic.
- The final vector contour extraction remains CPU/OpenCV by design.
- Focused screenshot evidence covers the screens changed most directly in this
  phase rather than the full historical layout-state catalog.

## Follow-Up Tasks

- Add focused layout captures for the dedicated candidate-selection surface once
  a deterministic screenshot state for that step is added to the layout script.
- Extend GPU acceleration deeper into candidate filtering if future profiling
  shows that stage dominates runtime after the selected-only tracking split.
