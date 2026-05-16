# Phase 10 Report

## Summary

- Added SQLite-backed correction history for local jobs and authenticated API track edits.
- Added local UI correction workflows for relabel, show/hide, export inclusion, delete, merge, split, add object, and repair prompts.
- Added edited review/export-inclusion state so corrections survive API refetches, app reloads, and browser reloads.
- Updated `/api/jobs/{jobId}/track-edits` and authenticated `/v1/jobs/{jobId}/track-edits` to apply deterministic artifact edits where possible.
- Added deterministic no-model partial-rerun hooks for add-object and repair requests with explicit unavailable diagnostics and `aiUsage: "none"`.
- Documented correction routes, supported operations, and current partial-rerun limitations.

The working tree was not clean at phase start. Pre-existing README and `out/demo` generated changes were left untouched.

## Changed Files

- `docs/developer_api.md`
- `docs/local_ui.md`
- `docs/roadmap/phase-10-report.md`
- `scripts/build_ui_shell.mjs`
- `scripts/phase10_correction_workflow_smoke.py`
- `scripts/test_ui_config_builder.mjs`
- `src/motionjson/backend/api.py`
- `src/motionjson/backend/corrections.py`
- `src/motionjson/backend/db.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_backend_api_product.py`
- `tests/test_backend_track_corrections.py`
- `tests/test_phase10_track_edit_workflows.py`

## Tests Run

- `python -m pytest tests -k track_edit` failed because `python` is not installed on this machine.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/backend/corrections.py src/motionjson/ui/server.py src/motionjson/backend/api.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k track_edit -q` — 7 passed, 198 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_backend_track_corrections.py tests/test_phase10_track_edit_workflows.py tests/test_phase9_ui_job_review_smoke.py -q` — 8 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_backend_track_corrections.py tests/test_phase10_track_edit_workflows.py tests/test_backend_api_product.py -q` — 13 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_backend_track_corrections.py tests/test_phase10_track_edit_workflows.py tests/test_local_ui_api.py tests/test_backend_api_product.py tests/test_backend_jobs_worker.py tests/test_mask_corrections.py -q` — 44 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` — 205 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 scripts/phase10_correction_workflow_smoke.py`
- `node --check src/motionjson/ui/static/app.js`
- `node --check scripts/build_ui_shell.mjs`
- `node scripts/test_ui_config_builder.mjs`
- `npm test` — 19 passed.
- `npm run lint`
- `npm run build`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help`
- Browser smoke at `http://127.0.0.1:8788/`: created a project/video, ran a mock job, relabeled a reviewed track through the correction UI, reloaded the page, confirmed the relabel/history persisted, and found no console errors.
- Browser smoke at `http://127.0.0.1:8789/`: created a project/video, ran a mock job, saved a repair request, reloaded the page, confirmed `repair_provider_unavailable` and partial-rerun diagnostics were visible in correction history, and found no console errors.
- `git diff --check`

## Known Limitations

- `add_object` and `repair_track` persist prompts and expose deterministic review hooks, but do not run model-assisted partial extraction yet.
- Synthetic add-object review tracks are placeholders until a repair/partial extraction worker materializes masks and cutouts.
- `/api/jobs/{jobId}/track-edits` and `/v1/jobs/{jobId}/track-edits` apply deterministic artifact edits for relabel, hide/show, delete, merge, and split. Full export/render worker consumption of correction state across every output format remains Phase 11 work.

## Follow-Up Tasks

- Add a real partial-rerun worker that materializes add-object and repair artifacts when a capable provider is available.
- Teach export/render workers to consume correction state directly for every export format, beyond edited artifacts and review/export-inclusion metadata.
- Add richer visual split/merge controls once edited track timelines are available in the UI.
