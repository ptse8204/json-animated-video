# Phase 3 Report - Extraction Job And Artifact Model

## Summary

Phase 3 added a shared local job artifact model for extraction runs. The CLI
still writes the existing MotionJSON output files in the same output directory,
and now also writes `run_config.json`, `job.json`, `events.jsonl`, `logs.txt`,
`metrics.json`, `artifacts.json`, and `provider_diagnostics.json`. Failed runs
write `failure.json` and append the raw traceback to `logs.txt`.

Backend extraction jobs use the same artifact writer inside the worker. Success
and failure artifacts are registered as generated backend assets, and coarse
progress events are mirrored into `job_events` for future API/UI polling.

The working tree was still not clean at the start of Phase 3 because of
pre-existing `README.md`, backup files, and generated `out/demo/*` changes left
unstaged from before Phase 0. Phase 3 changes were kept to job artifacts,
pipeline progress hooks, backend cancellation/artifact routes, tests, docs, and
this report.

## Subagent Findings

- `backend_cv_architect`: recommended a top-level artifact helper rather than a
  backend-only module, using the existing `--out` directory as the run artifact
  root to preserve CLI behavior.
- `qa_benchmark_engineer`: identified missing coverage for structured run
  artifacts, progress events, traceback failure diagnostics, cancellation, and
  real CLI compatibility.
- `reviewer`: flagged durable artifacts, failure diagnostics, granular progress,
  cancellation, and synchronous CLI wrapping as likely Phase 3 acceptance risks.

## Implementation

- Added `src/motionjson/job_artifacts.py` with:
  - `LocalJobRun`;
  - `JobCanceled`;
  - JSON/JSONL artifact writing;
  - event emission;
  - cooperative cancellation marker checks;
  - failure diagnostics and traceback logging;
  - artifact manifest and metrics generation.
- Extended `run_pipeline()` and `run_multi_object_pipeline()` with optional
  `job_context` progress/cancellation hooks. Default `None` preserves existing
  callers.
- Wrapped CLI extraction in `LocalJobRun` while preserving existing stdout and
  root output files.
- Added `mock` as a no-model CLI/config provider using the existing
  deterministic `MockSegmentationProvider`.
- Updated backend extraction jobs to write/register success and failure job
  artifacts.
- Added backend pending-job cancellation through `request_cancel_job()` /
  `mark_canceled()`, plus `cancel_requested` for cooperative running-job
  cancellation.
- Added `backend cancel-job`, `POST /v1/jobs/{jobId}/cancel`, and
  `GET /v1/jobs/{jobId}/artifacts`.
- Updated validation so output-directory validation skips auxiliary
  run-config/provider-diagnostics schemas while still validating core
  MotionJSON artifacts.
- Added docs in `docs/job_artifacts.md` and updated related docs.

## Compatibility Notes

- Existing CLI extraction outputs remain in the same locations.
- Existing backend worker success/failure status behavior remains intact.
- Backend provider policy remains deterministic local only: `threshold`,
  `external`, or `mock`.
- Job artifact JSON files use auxiliary `format` fields or skipped auxiliary
  schemas so `motionjson validate <output-dir>` continues to validate core
  MotionJSON files without treating job metadata as render payloads.
- Cancellation is cooperative. Pending backend jobs can be canceled before
  worker claim; running backend jobs persist `cancel_requested` and extraction
  checks cancellation between stages and sampled frames. Long provider calls may
  not interrupt until the provider returns.

## Review Findings Addressed

- Job-owned files and known generated extraction outputs are cleared at
  `LocalJobRun.initialize()` so reused output directories do not retain stale
  `failure.json`, logs, events, metrics, `cancel.requested`, objects, masks,
  previews, or root MotionJSON outputs.
- Running backend cancellation now persists `cancel_requested`, workers observe
  it through the job context, and final status becomes `canceled`.
- Backend artifact registration preserves `debug_frame`, `mask`, `cutout`, and
  `preview` kinds.
- Progress events expose monotonic `overallRatio` and optional `stageRatio`
  that is monotonic within each `(stage, objectId)` pair.

## Tests Run

Required command:

- `python -m pytest tests -k job` - failed because `python` is not on PATH in
  this shell.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_job_artifacts.py -q` - passed, 11 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_config.py tests/test_job_artifacts.py -q` - passed, 23 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k job -q` - passed, 21 tests, 125 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 146 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed and lists `mock`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed and lists `cancel-job`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend cancel-job --help` - passed.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check` - passed.

## Changed Files

- `src/motionjson/job_artifacts.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/cli.py`
- `src/motionjson/config.py`
- `src/motionjson/validation.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/backend/queue.py`
- `src/motionjson/backend/cli.py`
- `src/motionjson/backend/api.py`
- `tests/test_job_artifacts.py`
- `tests/test_config.py`
- `docs/job_artifacts.md`
- `docs/index.md`
- `docs/run_config.md`
- `docs/schemas.md`
- `docs/saas_backend.md`
- `docs/developer_api.md`
- `docs/roadmap/phase-3-report.md`

## Known Limitations

- Progress events are coarse. Discovery, propagation, and track linking emit
  `skipped` events until the provider pipeline refactor splits those stages.
- Cancellation cannot interrupt a provider call already inside OpenCV/SAM2 or a
  hosted request; it is checked between stages and sampled frames.
- Backend failure artifacts are registered for extraction worker failures. Other
  backend job types still use their existing failure path.
- `events.jsonl` is the source of detailed progress. SQLite `job_events` only
  mirrors coarse events and should not be treated as a complete artifact log.
- Artifact directories use the existing extraction output directory for CLI
  compatibility rather than a nested `runs/<id>/` project structure. A project
  directory layout can be added during UI/project phases.

## Follow-Up Tasks

- Phase 4: connect progress events to concrete provider pipeline stages.
- Phase 5: emit discovery candidate artifacts for non-manual discovery modes.
- Phase 6: add explicit object-track and raster-fallback reason models.
- Phase 7 and later UI/API phases: display `events.jsonl`, `artifacts.json`,
  `failure.json`, and cancellation state in the local UI.
