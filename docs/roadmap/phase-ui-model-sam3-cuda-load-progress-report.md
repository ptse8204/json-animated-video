---
historical: true
default_context: false
---

# Phase UI Model SAM3 CUDA Load Progress Report

## Summary

- Changed SAM3 Scene Sweep CUDA loading so `Sam3TrackerModel.from_pretrained(...)` uses a CUDA `device_map` and `low_cpu_mem_usage` before falling back to compatibility load paths.
- Stopped presenting elapsed-time-only heartbeats as successful progress. The setup events now report measured CUDA memory use and explicitly say `no model-sized CUDA allocation yet` when GPU memory is not increasing enough to prove model weight placement.
- Avoided a redundant `.to(cuda)` when Transformers already placed model parameters on CUDA during `from_pretrained`.
- Streamed the same SAM3 model-load progress labels into extraction candidate discovery events, so the Run monitor can show model/GPU state before keyframe mask generation begins.
- Documented the new CUDA load behavior and the recovery path for repeated no-allocation messages.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_provider_settings.py`
- `tests/test_sam3_providers.py`
- `docs/sam3_local.md`
- `docs/roadmap/phase-ui-model-sam3-cuda-load-progress-report.md`

## Tests Run

- `python3 -m pytest -q tests/test_provider_settings.py::test_sam3_cache_then_smoke_defaults_to_scene_sweep_without_checkpoint_path tests/test_provider_settings.py::test_sam3_cuda_smoke_fails_if_pipeline_loads_on_cpu tests/test_provider_settings.py::test_sam3_prepare_model_preserves_runtime_failure_status tests/test_sam3_providers.py::test_sam3_loader_heartbeat_reports_long_blocking_steps tests/test_sam3_providers.py::test_local_sam3_auto_masks_reports_scene_sweep_progress_events` - passed
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam3_providers.py` - 114 passed, 1 skipped
- `npm test` - passed
- `npm run build` - passed
- `python3 -m pytest -q` - 516 passed, 1 skipped in 53.37s
- `python3 -m motionjson.cli --help` - passed
- `python3 -m motionjson.cli extract --help` - passed
- `python3 -m motionjson.cli backend --help` - passed

## Known Limitations

- Automated tests still use mocked torch/Transformers. The real Colab acceptance check remains required after deploying this commit and restarting the UI/backend.
- The backend now reports measured CUDA allocation during model load, but a blocked Python library call is still not safely interruptible inside the current process. If a real Colab run continues to block before CUDA allocation, the next engineering step should isolate setup smoke in a killable subprocess.

## Follow-Up Tasks

- Rerun Prepare local model in the CUDA Colab notebook and verify the setup log moves from `Loading SAM3 Tracker weights with CUDA device_map=0` to `model_loaded_on_device` with a model-sized CUDA memory increase.
- If Colab still shows no model-sized CUDA allocation for several minutes, capture the exact setup events and install versions for `torch`, `transformers`, `accelerate`, and `safetensors`.
