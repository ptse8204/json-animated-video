---
historical: true
default_context: false
---

# Phase UI Model Runtime Report

## Summary

- Split SAM3 scene sweep configuration from the official SAM3 checkpoint path. `sam3TrackerModel` now defaults to `facebook/sam3`, accepts Hugging Face repo ids or local `from_pretrained` directories, and rejects single `.pt` files before Transformers runtime initialization.
- Kept `sam3ModelPath` scoped to official SAM3 package concept/exemplar workflows, with plain-language errors that direct users back to Model setup for scene sweep.
- Added the independent `sam2-hf-auto-masks` fallback provider using `facebook/sam2.1-hiera-large`, separate from official SAM2 checkpoint/config prompt tracking.
- Extended provider setup jobs with allowlisted cache-model actions, setup-state reporting, SAM2 HF fallback actions, explicit confirmation checks, cancel/retry visibility, and browser-safe redaction through the Local UI response layer.

## Changed Files

- `pyproject.toml`
- `src/motionjson/backend/models.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/cli.py`
- `src/motionjson/config.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/sam2.py`
- `src/motionjson/providers/sam3.py`
- `tests/test_capabilities.py`
- `tests/test_discovery_providers.py`
- `tests/test_provider_settings.py`
- `tests/test_sam2_providers.py`
- `tests/test_sam3_providers.py`

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/sam2.py tests/test_sam3_providers.py tests/test_sam2_providers.py`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_sam2_providers.py tests/test_provider_settings.py tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_config.py tests/test_capabilities.py tests/test_phase13_packaging_onboarding.py tests/test_local_ui_api.py`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`

## Known Limitations

- The cache-model job exposes a completed cache result only after `huggingface_hub.snapshot_download` returns; detailed byte-level progress is not available yet.
- Setup jobs can request cancellation, but an in-flight external pip install or Hugging Face download cannot always stop immediately.
- UI simplification and first-run model setup copy are intentionally left for the next phase.

## Follow-Up Tasks

- Wire the main Local UI to show one recommended model setup path by default and hide alternatives behind `Change model`.
- Add first-run UI tests for the setup state machine, failed-run recovery actions, and normal-mode simplicity constraints.
- Update docs and Colab to make UI-owned model setup the primary path and manual SAM paths an Advanced fallback.
