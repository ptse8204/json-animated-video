# Phase Platform Runtime Mask Sync Report

## Summary

Implemented a bounded platform/runtime stabilization phase for the MotionJSON Workspace. The phase cleans up active user-facing local-only wording, adds runtime accelerator proof fields, preserves real mask outline and frame-sync metadata through SAM outputs, opens review tools with explicit selected-run artifact URLs, and keeps desktop review/export layout evidence current.

Initial `git status` was clean. Internal compatibility ids such as `sam2-local`, `sam3-local`, and existing env/API storage keys were preserved.

## Changed Files

- `src/motionjson/provider_settings.py`, `src/motionjson/providers/sam3.py`, `src/motionjson/backend/worker.py`, `src/motionjson/capabilities.py`: runtime proof fields, CUDA/MPS/CPU reporting, platform-neutral provider copy.
- `src/motionjson/pipeline.py`, `src/motionjson/ui/server.py`, MotionJSON schemas: real outline metadata, source bbox, contour counts, mask area, and canonical frame maps in scene/review/export payloads.
- `src/motionjson/ui/static/app.js`, `index.html`, `config_builder.js`, `ui_selectors.js`, `app.css`: Workspace/Runtime API wording, accelerator badges, real artifact handoff URLs, frame-map-based review playback, requestVideoFrameCallback overlay scheduling, no square overlay fallback for missing outlines.
- `examples/object_selection_workflow.*`, `examples/timeline_editor.js`, `examples/landing_page.html`: run artifact handoff now errors loudly when selected-run artifacts are missing; `/out/demo` is limited to standalone demo mode.
- `src/motionjson/backend/assets.py`, `src/motionjson/backend/selected_tracking.py`, `src/motionjson/job_artifacts.py`: selected tracking can replace stale generated rows and review selected SAM tracking artifacts.
- `scripts/test_ui_config_builder.mjs`, `scripts/build_ui_shell.mjs`, Python tests: copy regression, runtime badge, artifact handoff, schema, provider proof, and selected-review coverage.
- `docs/design/screenshots/platform-runtime-mask-sync/`: before/after screenshot evidence.

## Browser Evidence

Captured before and after layout screenshots for:

- `workflow-review`
- `workflow-export`
- `job-review`
- `correction-tools`
- `model-setup-sam3-local`

Viewports:

- `mobile-390`
- `tablet-1024`
- `laptop-1366`
- `desktop-1440`
- `desktop-1920`

The final after run passed with nonblank review/export/job-review states. Desktop review and export are visually distinct: review presents preview plus object list; export presents package validation and included-object readiness.

## Tests Run

- `npm test`
- `npm run build`
- `npm run ui:layout -- --state workflow-review,workflow-export,job-review,correction-tools,model-setup-sam3-local --viewport laptop-1366,desktop-1440,desktop-1920,tablet-1024,mobile-390 --screenshot-dir docs/design/screenshots/platform-runtime-mask-sync/after`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_final_export.py`
- `PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q tests/test_mvp_contract.py::test_pipeline_writes_mvp_schema_and_profile tests/test_object_selection_workflow.py tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export`
- `python3 -m motionjson.cli --help && python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- This phase does not complete a full candidate-first complex-video redesign with manual keep/reject before any materialization. It strengthens the artifact/review boundary and selected tracking handoff that the candidate-first workflow will need.
- Merge/split/add-prompt/repair request persistence remains limited to the existing review action model unless a later phase expands backend editing semantics.
- CUDA/MPS runtime proof is validated by tests and smoke metadata. Real CUDA acceptance still requires running the completed patch in the target GPU runtime and confirming the UI badge reads `CUDA active`.
- Historical roadmap/docs still use older “Local UI” terminology where they describe prior phases. Active Workspace UI copy, CLI help, provider messages, and example tool copy were updated.

## Follow-Up Tasks

- Build the full candidate-first Scene Sweep flow: discover, preview outlines, accept/refine, then materialize.
- Add a moving-object fixture that asserts mask overlay center and raster cutout center remain within the planned 3 px tolerance after coordinate scaling.
- Expand persistent review edits for merge/split/add prompt/repair requests into explicit backend mutation endpoints.
- Run a real CUDA Colab acceptance pass and record the runtime proof fields in a debug report.
