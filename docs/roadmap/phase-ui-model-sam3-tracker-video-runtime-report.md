---
historical: true
default_context: false
---

# Phase UI Model SAM3 Tracker Video Runtime Report

## Summary

- Investigated the `Sam3VisionEncoderOutput` / `fpn_position_embeddings` failure reported from the Red Ball demo run.
- Confirmed this is a known upstream Hugging Face Transformers SAM3 Tracker Video bug, not a content/discovery failure.
- Made SAM3 Tracker Video propagation optional for normal Scene Sweep runs and added a compatibility detector so broken Transformers builds are reported before loading the video tracker.

## Cause

- MotionJSON's Scene Sweep run config enabled `useTransformersTracker` by default.
- That forced extraction to call the optional `Sam3TrackerVideoModel` path after automatic mask discovery.
- The user's Colab runtime hit the upstream Transformers bug fixed by Hugging Face PR #43487, where SAM3 video code referenced `fpn_position_embeddings`.
- Scene Sweep automatic masks do not require SAM3 Tracker Video. Requiring it made a normal extraction depend on a fragile optional propagation path.

## Changed Files

- `src/motionjson/providers/sam3.py`
  - Added `sam3_tracker_video_runtime_status()` to detect importability and the known `fpn_position_embeddings` bug by inspecting the installed Transformers SAM3 Tracker Video source.
  - Fails explicit Tracker Video requests fast with an actionable message when the broken runtime is detected.
- `src/motionjson/providers/discovery.py`
  - Uses keyframe mask sequences for Scene Sweep when Tracker Video is not explicitly requested.
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/ui/static/app.js`
  - Normal SAM3 Scene Sweep configs no longer enable `useTransformersTracker` by default.
- `src/motionjson/provider_settings.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/backend/provider_setup_jobs.py`
  - Treat Tracker Video as optional for normal Scene Sweep readiness.
  - Surface broken Tracker Video as an optional warning instead of blocking setup.
  - Install actions now run pip with `--upgrade`.
- `pyproject.toml`
  - Raises the SAM3 Transformers extra to `transformers>=5.3.0`.
- `docs/sam3_local.md`
  - Adds troubleshooting guidance for the `fpn_position_embeddings` runtime bug.
- `tests/test_sam3_providers.py`
- `tests/test_phase8_ui_config_builder.py`
- `scripts/test_ui_config_builder.mjs`
  - Adds regression coverage for the known broken Tracker Video runtime and the new default run config.

## Sources Checked

- Hugging Face Transformers issue #43475: `[SAM 3 Video] Sam3VisionEncoderOutput object has no attribute 'fpn_position_embeddings'`.
- Hugging Face Transformers PR #43487: merged fix for the `fpn_position_embeddings` SAM3 video bug.
- PyPI Transformers release history showing newer 5.x releases are available after the upstream fix.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/discovery.py src/motionjson/provider_settings.py src/motionjson/capabilities.py src/motionjson/backend/provider_setup_jobs.py`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_provider_settings.py tests/test_phase8_ui_config_builder.py`
- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_provider_settings.py tests/test_sam3_providers.py tests/test_phase8_ui_config_builder.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- Normal Scene Sweep now avoids the broken optional video tracker and produces reviewable keyframe mask sequences unless Tracker Video is explicitly enabled.
- True SAM3 video propagation still depends on a compatible installed Transformers runtime and a runtime restart after upgrading packages in Colab.

## Follow-Up Tasks

- Add a visible UI toggle for "experimental true video propagation" with the compatibility warning surfaced next to it.
- Add a review-page badge for candidates that used keyframe sequence fallback.
