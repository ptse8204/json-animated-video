# Phase UI Model Setup Flow Report

## Summary

Rebuilt the main Local UI around the six-panel storyboard flow: goal, video,
model setup, prepare/run, run recovery, and review/export. Model setup is now a
first-class step in the primary workflow, with SAM3 Scene Sweep recommended for
`Find everything in scene`, SAM2 fallback shown when compatible, and hosted SAM3
kept concept-only unless a profile advertises automatic masks.
SAM3 Scene Sweep diagnostics now gate readiness on the independent Transformers
automatic-mask path plus Tracker Video path and never report SAM2 as a blocker.

Added provider setup jobs for server-owned setup actions so the UI can install
optional extras, check access, diagnose, smoke-test, retry, cancel, and show
redacted logs without accepting arbitrary shell commands. Failed extraction jobs
now stay in the flow and expose `Open logs`, `Change setup`, `Run again`, and
`Choose different model`; only queued/running jobs block a new run.

Updated the Colab notebook to launch users into the same main UI Model setup
flow, keeping notebook cells as advanced fallback/debugging.

## Research Basis

- Hugging Face Transformers SAM3 Tracker automatic mask generation:
  https://huggingface.co/docs/transformers/model_doc/sam3_tracker
- Hugging Face Transformers SAM3 Tracker Video:
  https://huggingface.co/docs/transformers/model_doc/sam3_tracker_video
- Official SAM3 repository:
  https://github.com/facebookresearch/sam3

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/server.py`
- `src/motionjson/backend/db.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/provider_settings.py`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_provider_settings.py`
- `tests/test_local_ui_api.py`
- `tests/test_colab_notebooks.py`
- `tests/test_phase03b_provider_settings_ui.py`
- `tests/test_phase10_free_hosted_demos.py`
- `notebooks/colab_ui_provider_connect_demo.ipynb`
- `docs/security/api_keys.md`
- `docs/sam3_local.md`
- `docs/codex/codex_ui_flow_rebuild_prompt.md`
- `docs/design/screenshots/ui-model-setup-flow-before/`
- `docs/design/screenshots/ui-model-setup-flow/`

## Screenshot Evidence

- Storyboard reference copied to `docs/design/screenshots/ui-model-setup-flow/storyboard-reference.png`.
- Before screenshots captured in `docs/design/screenshots/ui-model-setup-flow-before/`.
- After screenshots captured in `docs/design/screenshots/ui-model-setup-flow/`.
- Viewports checked: `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.
- States checked: `workflow-goal`, `workflow-video`,
  `model-setup-sam3-local`, `prepare-sam3-trace-all`,
  `workflow-review-failure`, and `workflow-export`.

The after evidence confirms that the main lower content changes for each
Continue step, the Model setup screen exposes inline setup actions, Prepare
shows scene-sweep controls without manual prompts, and failed runs show recovery
actions in the Run monitor.

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `python3 -m py_compile src/motionjson/backend/provider_setup_jobs.py src/motionjson/provider_settings.py src/motionjson/ui/server.py tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_colab_notebooks.py tests/test_phase03b_provider_settings_ui.py tests/test_phase10_free_hosted_demos.py`
- `PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest`
  - Result: `474 passed, 1 skipped`
- `npm test`
  - Result: `21 passed`
- `npm run lint`
- `npm run build`
- `npm run ui:layout -- --state workflow-goal,workflow-video,model-setup-sam3-local,prepare-sam3-trace-all,workflow-review-failure,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-model-setup-flow`
  - Result: `status: ok`

The layout command emitted the existing non-fatal Python multiprocessing
`resource_tracker` semaphore warning during shutdown.

## Known Limitations

- Setup job cancellation marks the job canceled and prevents a successful
  finish from being reported, but it does not forcibly kill an already-running
  `pip install` subprocess.
- SAM3 Scene Sweep readiness is capability-gated by the local Transformers
  tracker runtime; actual model execution still depends on the installed model
  packages and hardware available on the user's machine.
- Some historical docs still refer to the older Model Connections name outside
  this phase's setup-flow and SAM3/Colab documentation changes.

## Follow-Up Tasks

- Replace remaining historical Model Connections references in broad product
  docs with the new Model setup language where they are still user-facing.
- Add a real SAM3 Scene Sweep runtime implementation behind the newly repaired
  UI/setup flow so `sam3_auto_masks` uses automatic masks plus tracker-video
  object tracking end to end.
- Add subprocess termination for setup jobs if a user cancels while an install
  command is still running.
