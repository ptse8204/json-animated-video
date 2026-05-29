# Phase UI Model SAM3 Tracking Start Frame Report

## Summary

- Fixed the Red Ball demo failure where SAM3 Scene Sweep candidate discovery succeeded, but extraction failed during SAM3 Tracker Video propagation with `Cannot determine the starting frame index`.
- The tracker propagation call now passes an explicit `start_frame_idx`, bounded `max_frame_num_to_track`, and disables progress-bar output for backend jobs.
- SAM3 Scene Sweep now falls back to the generated keyframe mask sequence when per-candidate video tracking fails, records a visible warning event, and still writes reviewable candidate masks instead of failing the entire run.

## Cause

- `LocalSAM3DiscoveryBackend._track_candidate_with_tracker_video()` added inputs to the SAM3 Tracker Video session, then called `model.propagate_in_video_iterator(session)` without a start frame.
- Current Transformers SAM3 Tracker Video runtimes can require `start_frame_idx` when a forward pass has not already run on the prompted frame.
- `_sam3_track_or_seed_sequence()` did not catch tracker propagation errors, so one candidate tracking failure caused the isolated subprocess and full extraction job to fail.

## Changed Files

- `src/motionjson/providers/sam3.py`
  - Passes `start_frame_idx=frame_index`, `max_frame_num_to_track=len(frames)`, and `show_progress_bar=False` to SAM3 Tracker Video propagation.
- `src/motionjson/providers/discovery.py`
  - Converts SAM3 per-candidate tracking failures into a logged warning and a keyframe-mask fallback sequence.
  - Redacts local filesystem-looking paths from fallback error text before writing warnings/events.
- `tests/test_sam3_providers.py`
  - Verifies SAM3 Tracker Video receives explicit propagation parameters.
  - Adds a regression for the exact start-frame error, proving candidates remain usable and reviewable.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/discovery.py src/motionjson/providers/sam3.py`
- `python3 -m pytest -q tests/test_sam3_providers.py -q`
- `python3 -m pytest -q tests/test_sam3_discovery_subprocess.py tests/test_discovery_providers.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`

## Known Limitations

- The fallback mask sequence is not true multi-frame SAM3 video tracking. It preserves a reviewable candidate and avoids a hard failure, but users may still need review/correction if the object moves substantially.
- Real CUDA/SAM3 runtime performance still depends on the installed Transformers/SAM3 build and Colab GPU memory.

## Follow-Up Tasks

- Add a UI badge for candidates that used keyframe-sequence fallback tracking.
- Add an advanced option to require true SAM3 Tracker Video propagation and fail candidates that cannot be tracked.
