---
historical: true
default_context: false
---

# Phase UI Model SAM3 Direct Loader Report

## Summary

- Replaced SAM3 Scene Sweep setup smoke with the direct Hugging Face Transformers `Sam3TrackerProcessor` + `Sam3TrackerModel` path instead of the opaque `pipeline("mask-generation")` constructor that stalled in the live Colab tab.
- Added setup progress heartbeats around the long blocking model-weight load and CUDA transfer steps, so the UI keeps receiving events while the backend is still working.
- Added a direct point-grid mask generator for SAM3 Scene Sweep warmup and extraction, using the recorded server-side cache path and the requested CUDA device.
- Updated the public runtime contract to report the direct SAM3 tracker runtime kind, and updated the Local UI setup checklist logic to recognize the new load/progress events.
- Extended tests so cache-to-smoke and extraction runtime paths prove direct `from_pretrained` loading, CUDA move, offline local-cache usage, warmup success, and heartbeat progress.

Research references checked:

- <https://huggingface.co/docs/transformers/model_doc/sam3_tracker>
- <https://huggingface.co/facebook/sam3>

The Hugging Face docs show both the high-level mask-generation pipeline and the lower-level tracker API. This phase moves MotionJSON's readiness path to the lower-level API because it gives us explicit progress boundaries for processor load, model weight load, CUDA move, and warmup inference.

## Changed Files

- `src/motionjson/providers/sam3.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_provider_settings.py`
- `tests/test_sam3_providers.py`
- `docs/roadmap/phase-ui-model-sam3-direct-loader-report.md`

## Tests Run

- `npm test` - passed
- `npm run build` - passed
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_sam2_providers.py tests/test_sam3_providers.py` - 135 passed, 1 skipped
- `python3 -m pytest -q` - 516 passed, 1 skipped in 52.02s
- `python3 -m motionjson.cli --help` - passed
- `python3 -m motionjson.cli extract --help` - passed
- `python3 -m motionjson.cli backend --help` - passed
- `git diff --check` - passed

## Browser Evidence

- Used the requested Chrome tab only, URL:
  `https://8766-gpu-l4-s-kkb-ass1a0-2y717dalaehtd-a.asia-southeast1-0.prod.colab.dev/ui/`
- Read-only inspection confirmed the live Colab UI was still on the old stalled state:
  `Loading SAM3 Tracker mask-generation pipeline` at `46%`.
- No layout screenshot was committed because this phase did not change Local UI layout, cards, spacing, or visual hierarchy. The UI change only teaches the existing checklist logic to recognize new backend event names.

## Known Limitations

- The full automated suite uses mocked CUDA and Transformers runtimes. A real Colab acceptance run still needs to pull this commit, restart the local UI/backend, and rerun Prepare local model with approved `facebook/sam3` access.
- The new heartbeat keeps setup visibly alive during blocking Hugging Face/PyTorch calls, but Python cannot safely interrupt an already-running `from_pretrained` or CUDA `.to(...)` call in the middle. Cancel remains best-effort until those calls return.

## Follow-Up Tasks

- Run the manual Colab acceptance flow after deploying this patch: Prepare local model, confirm direct loader progress, confirm CUDA memory rises beyond the small old pipeline allocation, run smoke, then run a small Scene Sweep extraction.
- Add hard subprocess isolation for heavyweight model setup if we need cancel to terminate blocked PyTorch/Hugging Face calls immediately.
