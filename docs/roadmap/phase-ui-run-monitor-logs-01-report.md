---
historical: true
default_context: false
---

# UI-RUN-MONITOR-LOGS-01 Report

## Summary

- Fixed the Run monitor log path so `Open logs` refreshes the selected job,
  opens the visible run-log panel, and renders job events in the normal Run
  screen instead of only relying on the Advanced rail.
- Added stale-progress detection for active jobs. Running jobs whose latest
  event has not updated for the watchdog window now show a clear
  `No progress update` warning while preserving cancel/watch actions.
- Added SAM3 Scene Sweep progress events around tracker model loading and
  keyframe mask generation so long `sam3_auto_masks` discovery work no longer
  appears frozen at the generic `discovering object candidates` event.
- Extended job detail/event API responses so `GET /api/jobs/{jobId}` includes
  redacted events and `GET /api/jobs/{jobId}/events` includes the selected job
  snapshot for robust log refreshes.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/server.py`
- `src/motionjson/providers/sam3.py`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `tests/test_local_ui_api.py`
- `tests/test_sam3_providers.py`
- `docs/roadmap/phase-ui-run-monitor-logs-01-report.md`
- `docs/design/screenshots/ui-run-monitor-logs-01-before/`
- `docs/design/screenshots/ui-run-monitor-logs-01/`

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `node --check scripts/check_local_ui_layout.mjs`
- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/ui/server.py tests/test_sam3_providers.py tests/test_local_ui_api.py`
- `npm test`
- `npm run build`
- `python3 -m pytest tests/test_local_ui_api.py tests/test_job_lifecycle.py tests/test_sam3_providers.py -q`
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_api_queues_mock_job_and_scrubs_storage_keys -q`
- `npm run ui:layout -- --state workflow-run-stale,workflow-run-logs-open --screenshot-dir docs/design/screenshots/ui-run-monitor-logs-01`
- `rg -n "<provided_hf_token_or_distinctive_fragments>" . --glob '!node_modules/**' --glob '!.venv/**'`
- `git diff --check`

The layout commands passed and emitted the existing non-fatal Python
`resource_tracker` leaked semaphore warning at shutdown.
The token scan returned no matches.

## Browser Evidence

- Before screenshots: `docs/design/screenshots/ui-run-monitor-logs-01-before/`
  with 13 files for existing Run and failed-review log states.
- After screenshots: `docs/design/screenshots/ui-run-monitor-logs-01/` with
  12 files covering stale active runs and open-log active runs.
- Viewports checked: `390x844`, `768x1024`, `1024x768`, `1366x768`,
  `1440x900`, and `1920x1080`.

## Known Limitations

- The stale detector is a UI/API visibility guard, not a worker watchdog that
  terminates long model calls. Long SAM3 calls can still continue after the
  warning appears, and cancellation remains cooperative.
- Existing jobs that are already blocked inside model code only gain the UI
  stale warning after the browser polls their last event timestamp; the new
  finer-grained SAM3 progress events apply to subsequent scene-sweep runs.

## Review

- Ran one read-only diff-review scout before commit.
- Scout requested this report and an expanded redaction regression for embedded
  job events. Both were addressed before commit.

## Follow-Up Tasks

- Consider adding a backend worker heartbeat or timeout policy for model calls
  that do not return control to the Python pipeline for several minutes.
