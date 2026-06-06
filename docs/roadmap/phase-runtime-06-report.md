# Phase runtime-06: SAM3 scene sweep in-flight diagnostics

## Summary

Added inner-operation logging for SAM3 Scene Sweep so UI debug reports can
identify where a run is blocked instead of only reporting silence during
`candidate_discovery`.

The previous log contract emitted heartbeats from the outer worker and
`SAM3 object candidate ... generated` only after a candidate completed. That
left the most important gap: if a Colab/CUDA run went quiet between two
candidate events, the debug report could not distinguish model inference,
input preparation, postprocessing, candidate filtering, tracking, mask writes,
preview writes, or parent/subprocess waiting.

This phase records those boundaries explicitly and makes the isolated
subprocess report its last child event while it waits or times out.

## Changed Files

- `src/motionjson/providers/sam3.py`
  - Emits scene-sweep keyframe start/finish events.
  - Emits generator call, normalization, input preparation, SAM3 inference, and
    SAM3 mask-postprocess start/finish events with elapsed timing where known.
  - Passes an optional progress callback into compatible SAM3 generators without
    breaking generators that do not accept the extra keyword.
- `src/motionjson/providers/discovery.py`
  - Emits per-candidate start, filter, skip, tracking, mask-write,
    preview-write, and finish events with object id, record index, keyframe,
    bbox, mask metrics, and elapsed timing where known.
- `src/motionjson/backend/sam3_discovery_subprocess.py`
  - Tracks the last child progress event from the isolated SAM3 process.
  - Emits `sam3_discovery_subprocess_waiting` every 30 seconds while the parent
    is alive but waiting for the child.
  - Includes `lastChildEvent`, elapsed subprocess time, and seconds since child
    event in wait and timeout metadata.
  - Adds the last in-flight operation to timeout messages so copied UI debug
    reports remain useful even when metadata is not expanded.
- `tests/test_sam3_providers.py`
  - Covers the new scene-sweep inner event contract.
- `tests/test_sam3_discovery_subprocess.py`
  - Covers timeout reporting with a child `sam3_inference_started` event.
- `docs/sam3_local.md`
  - Documents the new event names and how to interpret stuck runs.
- `docs/local_ui.md`
  - Notes that UI debug reports now include the last SAM3 in-flight operation.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/discovery.py src/motionjson/backend/sam3_discovery_subprocess.py src/motionjson/backend/sam3_discovery_worker.py`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_sam3_discovery_subprocess.py`
- `python3 -m pytest -q tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_local_ui_api.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_sam3_providers.py tests/test_sam3_discovery_subprocess.py`
- `python3 -m pytest -q tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_local_ui_api.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_sam3_providers.py tests/test_sam3_discovery_subprocess.py tests/test_final_export.py tests/test_track_filtering.py tests/test_job_artifacts.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- This phase improves diagnosis; it does not change SAM3 mask quality,
  candidate scoring, or extraction throughput.
- If a third-party SAM3 call blocks inside native CUDA/PyTorch code, Python
  still cannot emit a nested progress event until the call returns. The timeout
  and wait events now identify that the last in-flight operation was model
  inference instead of making it look like a generic UI or heartbeat issue.
- Resource utilization still needs separate runtime telemetry if we want to
  correlate low GPU usage with CPU preprocessing, disk writes, IPC waits, or
  synchronization stalls.

## Follow-Up Tasks

- Add optional per-run telemetry snapshots for CPU load, CUDA memory allocated,
  CUDA memory reserved, GPU utilization when available, RSS memory, and disk
  write timing.
- Surface `lastChildEvent` in the selected-run panel and copied debug report as
  a first-class "last in-flight operation" row.
- Add a slow-candidate threshold that marks individual SAM3 records as
  pathological and skips or isolates them without blocking the full scene sweep.
