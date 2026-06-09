# UI-WORKFLOW-13 Phase Report - Correct Inline Workflow Gaps

## Summary

UI-WORKFLOW-13 finishes the corrective UX pass after the keyframe-first work:

- Removed the normal all-panels workflow toggle and kept advanced tracing tasks
  visible inline on the Start screen.
- Added an explicit scan-frame chooser for `Pick objects from one frame` and
  blocked preview, validation, guided start, and local job start until the user
  confirms the exact frame.
- Registered candidate-scan preview artifacts while the job is still running and
  populated the main run monitor with live candidate, mask, and cutout previews.
- Kept SAM3 local setup token-first by sorting required inputs so Hugging Face
  token/access appears before optional provider details.
- Reworked the export subscreen so candidate filters and correction panels do
  not appear above the export gate. Export now starts with readiness, included
  objects, rights notes, then review/handoff tools.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/modules/state_store.js`
- `src/motionjson/ui/static/modules/workflow.js`
- `src/motionjson/pipeline.py`
- `src/motionjson/backend/worker.py`
- `scripts/build_ui_shell.mjs`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_fast_keyframe_workflow.py`
- `tests/test_ui_first_run_simplicity.py`
- `docs/roadmap/ui_model_connector_plan.md`
- `codex_tasks.yaml`
- `docs/local_ui.md`
- `docs/onboarding.md`
- `docs/first_run.md`

## Browser Evidence

Before screenshots:

- `docs/design/screenshots/ui-workflow-13-before/`

After screenshots:

- `docs/design/screenshots/ui-workflow-13/`

Captured states:

- `first-run`
- `model-setup-sam3-local`
- `prepare-pick-frame`
- `workflow-run`
- `candidate-review`
- `correction-tools`
- `export-gate`

Captured viewports:

- `390x844`
- `768x1024`
- `1024x768`
- `1366x768`
- `1440x900`
- `1920x1080`

The in-app Browser MCP tool was not exposed by tool discovery in this session,
so the repository headless Chrome layout/screenshot tooling was used.

## Tests Run

```bash
npm run build
npm test
npm run lint
node scripts/test_ui_config_builder.mjs
python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_fast_keyframe_workflow.py
python3 -m pytest -q tests/test_image_classifier.py tests/test_model_setup_recommendations.py
python3 -m pytest -q tests/test_local_ui_api.py tests/test_backend_api_product.py tests/test_backend_jobs_worker.py tests/test_job_artifacts.py tests/test_job_lifecycle.py
python3 -m motionjson.cli --help
python3 -m motionjson.cli ui --help
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-workflow-13 --state first-run,model-setup-sam3-local,prepare-pick-frame,workflow-run,candidate-review,correction-tools,export-gate --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920
git diff --check
```

## Known Limitations

- CUDA/MPS raster acceleration remains capability gated. CPU fallback remains
  the stable default, and final contour polygon extraction still ends on CPU for
  output stability.
- The no-token classifier uses local public torchvision weights when available;
  environments without torchvision or first-use weight access fall back to
  provider/user labels without blocking extraction.
- `docs/design/screenshots/model-setup-rescue-before/` was already untracked
  before this phase and was left untouched.

## Follow-Up Tasks

- Add a real-time browser test that starts a mock job and asserts live preview
  cards update during polling, not only through fixture screenshots.
- Expand GPU benchmark coverage once CUDA hardware is available in CI or a
  reproducible local benchmark profile.
