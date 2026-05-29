# Phase Report: SAM3 Subprocess Frame Metadata

## Summary

This phase fixes the next actual-video SAM3 Scene Sweep subprocess failure:

`SAM3 isolated scene sweep failed: 'types.SimpleNamespace' object has no attribute 'index'`

The isolated worker was reconstructing sampled frames with only `rgb`. The shared SAM3 discovery and tracking code expects the normal sampled `Frame` contract: `index`, `out_index`, `time_sec`, and `rgb`. The subprocess frame store now serializes that metadata, and the worker rebuilds real `Frame` and `VideoInfo` objects.

The phase also removes the misleading artificial `100%` progress from failed job events. Failed jobs now preserve the last real progress event instead of reporting completion.

## Changed Files

- `src/motionjson/backend/sam3_discovery_subprocess.py`
  - Stores frame index, sampled output index, and timestamp alongside RGB arrays.
- `src/motionjson/backend/sam3_discovery_worker.py`
  - Restores sampled frames as `Frame` objects and video metadata as `VideoInfo`.
- `src/motionjson/job_artifacts.py`
  - Stops failed jobs from emitting `overallRatio: 1.0`.
- `src/motionjson/backend/job_lifecycle.py`
  - Failed jobs with no known progress now report `0%` and `Failed`, not complete.
- `tests/test_sam3_discovery_subprocess.py`, `tests/test_job_artifacts.py`, `tests/test_job_lifecycle.py`
  - Added regression coverage for worker frame restoration and failed progress reporting.

## Tests Run

- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_job_artifacts.py::test_job_failure_event_does_not_report_artificial_100_percent tests/test_job_lifecycle.py::test_job_lifecycle_summarizes_failure_and_recovery_action`
- `python3 -m py_compile src/motionjson/backend/sam3_discovery_subprocess.py src/motionjson/backend/sam3_discovery_worker.py src/motionjson/job_artifacts.py src/motionjson/backend/job_lifecycle.py`
- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_job_artifacts.py tests/test_job_lifecycle.py tests/test_backend_jobs_worker.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`

## Known Limitations

- CI still uses fake subprocess/runtime coverage and does not prove real Colab CUDA SAM3 weights complete inference.
- A running Colab backend must be restarted before this fix is active.
- Existing failed jobs retain old event history; rerun extraction after restart.

## Follow-Up Tasks

- Retest a real Colab SAM3 Scene Sweep extraction after restart.
- If a new failure appears, inspect the isolated worker error; it should now be past frame reconstruction and into real SAM3 discovery/tracking behavior.
