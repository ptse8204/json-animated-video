---
historical: true
default_context: false
---

# Phase runtime-07: SAM3 diagnostic hardening

## Summary

Strengthened SAM3 Scene Sweep diagnostics so copied UI debug reports can answer
which candidate and inner operation are currently in flight, whether the
isolated subprocess is alive, whether parent/child IPC is waiting, and whether
best-effort GPU/stack evidence is available.

This phase does not change SAM3 model behavior, candidate quality, or output
selection. It changes the run/debug contract so stalled Colab runs are
actionable from job events and the UI debug report instead of requiring terminal
inspection.

## Changed Files

- `src/motionjson/providers/sam3.py`
  - Added canonical SAM3 operation metadata helpers.
  - Added shared operation ids/status/kind fields around grid prep, input prep,
    model inference, postprocess, keyframe generation, generator calls, and
    output normalization.
  - Added best-effort CUDA memory snapshots around inference/postprocess.
- `src/motionjson/providers/discovery.py`
  - Added `sam3_candidate_record_started` and
    `sam3_candidate_object_bound` events so the next record after a completed
    candidate is visible.
  - Added operation metadata for filtering, tracking, fallback tracking,
    candidate mask writes, preview writes, and final candidate completion.
  - Added per-frame mask encode/write diagnostics with frame number, source
    frame, mask area, shape, byte size, and elapsed ms.
- `src/motionjson/backend/sam3_discovery_subprocess.py`
  - Tracks current open child operations and reports `currentOperation` in wait
    and timeout events.
  - Adds subprocess liveness, return code, stdout/stderr reader liveness, and
    seconds since stdout/stderr/child event.
  - Adds best-effort `nvidia-smi` GPU sampling for Colab/CUDA runs.
  - Adds best-effort stack probe requests after
    `MOTIONJSON_SAM3_STACK_PROBE_SECONDS` seconds.
- `src/motionjson/backend/sam3_discovery_worker.py`
  - Registers `faulthandler`/`SIGUSR1` stack dumps for the isolated worker when
    supported.
- `src/motionjson/backend/job_lifecycle.py`
  - Preserves selected diagnostic metadata in `latestEvent`.
  - Adds `inflightOperation` to lifecycle summaries.
- `src/motionjson/ui/static/app.js`
  - Adds `## In-flight Diagnostics` to copied debug reports.
  - Enriches recent events with operation, object, record, frame, subprocess,
    and GPU probe fields.
- `docs/sam3_local.md`, `docs/local_ui.md`
  - Document the new diagnostic fields and how to interpret them.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/discovery.py src/motionjson/backend/sam3_discovery_subprocess.py src/motionjson/backend/sam3_discovery_worker.py src/motionjson/backend/job_lifecycle.py`
- `node --check src/motionjson/ui/static/app.js scripts/test_ui_config_builder.mjs`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_sam3_discovery_subprocess.py tests/test_discovery_providers.py tests/test_job_lifecycle.py`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_sam3_discovery_subprocess.py tests/test_discovery_providers.py tests/test_job_lifecycle.py tests/test_local_ui_api.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- GPU utilization is sampled with `nvidia-smi` only when present. A low sampled
  utilization value does not prove CUDA was never used; it proves what was
  visible at the sample time.
- Python stack probing uses `faulthandler` and `SIGUSR1` only where supported.
  Unsupported platforms report probe status instead of failing the job.
- If a native CUDA/PyTorch call blocks, Python stack data may only identify the
  call boundary. That is still useful because it distinguishes model/native
  blocking from Python postprocess, mask encoding, file I/O, or IPC waiting.
- This phase does not reduce workload, change auto-tuning, improve mask quality,
  or skip pathological candidates. It makes those follow-up fixes measurable.

## Follow-Up Tasks

- Add slow-candidate policy: skip or isolate a candidate whose operation exceeds
  a configurable threshold while preserving prior partial results.
- Add a UI row in the selected-run panel for `inflightOperation`, not only the
  copied debug report.
- Add optional Colab-specific resource telemetry for CPU percent, RSS memory,
  disk throughput, and CUDA allocated/reserved deltas over time.
