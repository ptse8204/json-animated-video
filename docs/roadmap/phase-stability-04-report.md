---
historical: true
default_context: false
---

# Phase Stability 04 Report

## Summary

- Started from a clean working tree after Phase Stability 03.
- Kept the first UI simplification pass in `app.js` to avoid import/loading
  risk.
- Extracted pure snapshot selectors for:
  - workflow job status;
  - model setup status;
  - recovery actions;
  - export availability;
  - primary action;
  - blocked reason.
- Updated `workflowStepContractFromSnapshot()` and
  `screenContractFromSnapshot()` so they consume snapshot values instead of
  reading the DOM or mutable UI state.
- Moved DOM/state collection into the `workflowSnapshot()` adapter.

## Changed Files

- `src/motionjson/ui/static/app.js`
  - Adds product-state selectors that accept plain snapshot objects.
  - Keeps render code behavior-compatible while routing primary action,
    blocked reason, model setup, job status, recovery, and export decisions
    through selector outputs.
  - Extends `workflowSnapshot()` with form values, selected job data, setup
    state, export validation, included/pending ids, and fallback counts.
- `scripts/test_ui_config_builder.mjs`
  - Adds selector contract tests.
  - Verifies workflow/screen selectors do not call `document.querySelector()`
    by installing a throwing document stub during selector calls.
- Screenshot evidence added under
  `docs/design/screenshots/phase-stability-04/`.

## Tests Run

- `node scripts/test_ui_config_builder.mjs`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_track_filtering.py tests/test_job_artifacts.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `npm run ui:layout -- --state workflow-run-asset-stalled,workflow-review --screenshot-dir docs/design/screenshots/phase-stability-04`
- `git diff --check`
- `sed -n '900,1395p' src/motionjson/ui/static/app.js | rg -n "state\\.|document|localStorage|querySelector|\\$\\(" -S || true`

## Browser Evidence

- Captured `workflow-run-asset-stalled` and `workflow-review` across:
  - `mobile-390`
  - `tablet-768`
  - `tablet-1024`
  - `laptop-1366`
  - `desktop-1440`
  - `desktop-1920`
- The layout smoke returned `status: ok`.
- Python emitted a shutdown resource-tracker warning for one leaked semaphore
  during layout smoke teardown; no layout failure was reported.

## Known Limitations

- The selectors remain in `app.js`. This is deliberate for the first pass; a
  separate module can follow once the selector contract has more coverage.
- `workflowSnapshot()` is still a large adapter because it is the single place
  where render-time DOM and state values are gathered.
- The selector purity scan covers the refactored selector region, not every UI
  helper in the file.

## Follow-Up Tasks

- Move mature selectors into a small dedicated module only after the tests prove
  the contract is stable.
- Continue reducing `workflowSnapshot()` by grouping adapter fields around
  model setup, job status, and export state.
- Add fixture tests for typed asset-prep partial recovery once the UI receives
  richer failed-frame metadata from the backend lifecycle payload.
