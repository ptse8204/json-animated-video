# Phase UI Model SAM3 Extraction Isolation Report

## Summary

- Confirmed the user's Run monitor stall was not the setup path. Extraction was still loading SAM3 in the main Local UI worker through `LocalSAM3DiscoveryBackend._ensure_tracker_mask_generator()`.
- Added an isolated SAM3 Scene Sweep extraction worker process. It runs the real `SAM3AutoMasksDiscoveryProvider` candidate proposal path, streams progress back to Run monitor, writes candidate artifacts into the run output directory, and returns `ObjectCandidate` records to the existing pipeline.
- Added a hard extraction timeout so a blocked Transformers/PyTorch model load fails the job cleanly instead of leaving it active forever.
- Kept cached model paths backend-only and redacted from streamed events.

## Changed Files

- `src/motionjson/backend/sam3_discovery_subprocess.py`
  - New parent-side provider/runner for SAM3 auto-mask extraction in a killable subprocess.
- `src/motionjson/backend/sam3_discovery_worker.py`
  - New child worker that loads sampled frames, runs SAM3 scene sweep proposal, writes candidate results, and streams progress events.
- `src/motionjson/backend/worker.py`
  - Server-side cached SAM3 runtime now uses the isolated extraction provider.
  - Added `MOTIONJSON_SAM3_EXTRACTION_TIMEOUT_SECONDS`, defaulting to 1800 seconds.
- `tests/test_sam3_discovery_subprocess.py`
  - Covers candidate return, event redaction, timeout, and worker termination.
- `tests/test_provider_settings.py`
  - Updated cached-runtime provider assertions for the isolated provider.
- `docs/sam3_local.md`
  - Documents extraction isolation, timeout configuration, and recovery guidance.

## Tests Run

- `python3 -m py_compile src/motionjson/backend/sam3_discovery_subprocess.py src/motionjson/backend/sam3_discovery_worker.py src/motionjson/backend/worker.py`
- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_provider_settings.py::test_worker_cached_runtime_providers_require_verified_runtime_without_public_config_leak tests/test_sam3_smoke_subprocess.py`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam3_providers.py tests/test_sam3_smoke_subprocess.py tests/test_sam3_discovery_subprocess.py tests/test_backend_jobs_worker.py`
- `npm test`
- `npm run build`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- Real Colab acceptance still needs the UI/backend restarted with this commit. The currently running Colab job will not inherit this change.
- The isolated extraction worker serializes sampled frames to a temporary compressed NumPy store before launching SAM3. That keeps the child process independent but adds overhead proportional to sampled frame count and resolution.
- This makes blocked model load recoverable and observable. It does not guarantee the upstream Transformers/SAM3 runtime will successfully load on every CUDA package combination.

## Follow-Up Tasks

- In Colab, restart the Local UI backend, rerun Prepare local model, then rerun Scene Sweep extraction. Confirm Run monitor reaches keyframe mask generation or fails with `scene sweep extraction timed out` instead of staying at model-weight load indefinitely.
- If model load still stalls around the same CUDA allocation, collect `torch`, `transformers`, `accelerate`, and `safetensors` versions from the runtime and decide whether to pin a known-good SAM3 Transformers stack.
