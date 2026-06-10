---
historical: true
default_context: false
---

# Phase runtime-03: Extraction-time runtime proof

## Summary

This phase closes the Colab/CUDA reporting gap where a completed or failed SAM3
run could show `runtimeProofStatus: not reported` even though the notebook
runtime had a GPU. Extraction jobs now record runtime proof from the actual
worker process before model work starts, then prefer stronger SAM3 subprocess
model-placement proof when it becomes available.

No layout surfaces were changed in this phase, so browser screenshot evidence
was not required.

## Changed files

- `src/motionjson/backend/worker.py`
  - Adds an extraction-worker environment proof for SAM/SAM3 jobs.
  - Emits `runtime_environment_proof_recorded` before heavyweight model work.
  - Fails real SAM3 CUDA runs early with `gpu_device_mismatch` when PyTorch in
    the worker cannot see CUDA.
  - Keeps explicit mock SAM3 discovery no-model safe.
- `src/motionjson/providers/sam3.py`
  - Adds `scene_sweep_runtime_proof_from_generator(...)`.
  - Exposes loaded SAM3 scene-sweep model placement through
    `LocalSAM3DiscoveryBackend.runtime_proof()`.
- `src/motionjson/backend/sam3_discovery_worker.py`
  - Emits runtime proof from the isolated SAM3 scene-sweep process after model
    load/proposal work.
- `src/motionjson/backend/job_lifecycle.py`
  - Prefers latest event runtime proof over an earlier stored result proof, so
    verified model-placement proof can supersede environment-only proof.
- `src/motionjson/ui/static/app.js`
  - Distinguishes `CUDA available` from `CUDA active`.
  - Keeps `CUDA active` for verified model placement instead of environment
    visibility alone.
- `scripts/test_ui_config_builder.mjs`
  - Adds badge tests for environment-only CUDA/MPS availability.
- `tests/test_backend_jobs_worker.py`
  - Adds worker runtime proof tests for CUDA-visible and CUDA-mismatch cases.
- `tests/test_sam3_providers.py`
  - Adds CPU-only fake-generator coverage for SAM3 loaded-on-CUDA proof.
- `tests/test_job_lifecycle.py`
  - Proves event runtime proof overrides earlier environment-only result proof.
- `docs/local_ui.md` and `docs/sam3_local.md`
  - Document environment proof versus model-placement proof.

## Tests run

- `python3 -m py_compile src/motionjson/backend/worker.py src/motionjson/backend/job_lifecycle.py src/motionjson/backend/sam3_discovery_worker.py src/motionjson/providers/sam3.py`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py::test_worker_runtime_environment_proof_reports_cuda_without_model_claim tests/test_backend_jobs_worker.py::test_worker_runtime_environment_cuda_mismatch_blocks_real_sam3 tests/test_sam3_providers.py::test_scene_sweep_runtime_proof_reports_loaded_cuda_from_generator tests/test_job_lifecycle.py::test_job_lifecycle_recovers_runtime_proof_from_events`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_job_artifacts.py tests/test_final_export.py tests/test_sam3_providers.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known limitations

- Environment proof does not prove model placement. It intentionally records
  `loadedOnCuda: false` until model placement is observed.
- The SAM3 subprocess model-placement proof is emitted after candidate proposal
  returns; if model loading hangs and times out before a generator exists, the
  run will still show environment proof plus the timeout failure.
- CPU-only and mock test paths remain no-model safe and do not import heavy SAM
  dependencies.

## Follow-up tasks

- Surface `CUDA available` versus `CUDA active` more prominently in the Run
  monitor details.
- Add the same model-placement proof pattern to future non-SAM3 heavy runtimes
  when they run in isolated workers.
- Move expensive candidate materialization behind review acceptance to reduce
  asset-prep work for complex runs.
