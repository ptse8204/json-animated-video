# Phase 1 Report - Authoritative Job Lifecycle Contract

## Summary

Phase 1 added a provider-neutral job lifecycle contract that the backend and
frontend can share without removing existing API fields. Jobs returned from the
Local UI now include a `lifecycle` block with normalized status, phase,
progress, provider summary, latest event, failure summary, review summary,
action gates, and a single next action. `GET /api/workspace` and
`GET /api/progress?projectId=...` now include a `jobCenter` block with active
and recent lifecycle-backed jobs.

The implementation keeps existing routes compatible and avoids hosted calls,
new heavy dependencies, or frontend behavior changes in this phase.

## Changed Files

- `src/motionjson/backend/job_lifecycle.py`
- `src/motionjson/ui/server.py`
- `tests/test_job_lifecycle.py`
- `docs/local_ui.md`
- `docs/roadmap/phase-flow-rebuild-1-report.md`

## Behavior Added

- `motionjson.job_lifecycle.v0.1` lifecycle summaries normalize existing job
  rows, events, review payloads, and provider/run config details.
- Unknown progress is represented with `progress.known: false`; event-measured
  progress remains `known: true`.
- Provider summaries keep provider ID, connection ID, display label, engine,
  locality, and hosted-call state separate.
- Failed and canceled jobs include plain-language failure/recovery summaries.
- Review summaries count candidates, selected candidates, tracks, exportable
  tracks, pending review tracks, diagnostics, raster fallback, and vector
  unavailable reason.
- Action gates expose `canCancel`, `canRetry`, `canReview`,
  `canTrackSelected`, and `canExport`.
- `jobCenter` exposes active and recent jobs for workspace/progress views.

## Tests Run

- `python3 -m pytest -q tests/test_job_lifecycle.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py` - passed, 50 tests.
- `npm test` - passed, 21 Node tests.

## Known Limitations

- `canRetry` is intentionally false because there is no stable retry endpoint
  yet. Later phases can enable it only after a safe explicit retry route exists.
- Lifecycle phases are derived from current job rows/events/review artifacts.
  They are conservative and do not require worker schema changes.
- Existing scalar `progress` and `percent` fields remain for compatibility even
  though new UI work should prefer `lifecycle.progress`.
- This phase does not rebuild the frontend Job Center; it provides the
  normalized backend contract for the next phases.

## Follow-Up Tasks

- Update frontend selectors to consume `job.lifecycle` instead of deriving job
  readiness from DOM/state fragments.
- Render `jobCenter` as the primary run monitor after starting jobs.
- Add a safe retry endpoint before exposing retry as an enabled action.
- Keep provider labels display-only in UI logic and compare provider IDs,
  connection IDs, engine, locality, and readiness instead.
