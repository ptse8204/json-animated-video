---
historical: true
default_context: false
---

# Phase Stability 01 Report

## Summary

- Added per-frame asset-preparation start/finish events with frame, object,
  bbox, mask area, file paths, byte sizes, crop dimensions, and elapsed time.
- Added object-level asset-preparation finished/failed events and durable
  `objects/<objectId>/failure.json` diagnostics.
- Added object-scoped checkpoint registration for backend extraction jobs so
  completed object artifacts are registered before later objects run.
- Added idempotent generated asset registration by `rel_path` so partial
  checkpoints and final output-tree registration do not duplicate asset rows.
- Added Local UI review metadata support for checkpointed object manifests when
  a final scene graph is not available yet.

## Changed Files

- `src/motionjson/pipeline.py`
  - Emits detailed frame-level asset-prep events.
  - Writes object failure diagnostics and invokes optional object checkpoints.
- `src/motionjson/backend/assets.py`
  - Adds generated asset lookup and register-once helper by generated rel path.
- `src/motionjson/backend/worker.py`
  - Preserves custom event names and registers object-scoped checkpoints.
- `src/motionjson/job_artifacts.py`
  - Classifies nested object `failure.json` files as failure diagnostics.
- `src/motionjson/ui/server.py`
  - Reads `object_manifest` artifacts into review objects/tracks.
- Tests updated in `tests/test_provider_pipeline.py`,
  `tests/test_job_artifacts.py`, and `tests/test_job_lifecycle.py`.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_provider_pipeline.py::test_multi_object_pipeline_checkpoints_completed_object_before_later_failure tests/test_job_artifacts.py::test_backend_extract_job_registers_structured_artifacts_and_progress tests/test_job_lifecycle.py::test_object_manifest_review_surfaces_partial_track_metadata`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_job_artifacts.py tests/test_provider_pipeline.py tests/test_job_lifecycle.py tests/test_backend_jobs_worker.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/backend/assets.py src/motionjson/backend/worker.py src/motionjson/pipeline.py src/motionjson/job_artifacts.py src/motionjson/ui/server.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `git diff --check`

## Browser Evidence

- Not required for this phase. No Local UI layout, visual hierarchy, cards,
  panels, or responsive behavior changed.

## Known Limitations

- Object checkpoints register completed object files, but full scene-level
  artifacts such as `scene_graph.json`, `tracks.json`, and web manifests still
  require the final export phase.
- A hard process death can only preserve objects checkpointed before death. It
  cannot emit the object-failed event for the object that killed the process.
- Register-once keeps the first generated row for a rel path within a job. This
  is correct for completed object checkpoints, but future retry-in-place
  behavior should explicitly version or update generated assets.

## Follow-Up Tasks

- Add memory-bounded track summaries and strip retained `rgb`/`mask` arrays
  after object checkpointing.
- Add per-frame timeout watchdog semantics using the new
  `asset_preparation_frame_started` and `asset_preparation_frame_finished`
  events.
- Show partial object checkpoints more explicitly in the Run monitor and Review
  UI once selector seams are extracted.
