# Phase runtime-05: Video-aware adaptive scene sweep tuning

## Summary

Revised Local UI auto tuning so SAM3 Scene Sweep parameters are derived from
video facts instead of fixed effort presets alone.

The previous helper treated `maxFrames` as a static cap. That meant a
10-second high-quality run at 12 fps could still cap at 96 frames, and retry
logic could reduce the run to 32-36 frames without explaining that the result
would become sparse or front-loaded. The new tuning is coverage-first: it
estimates the frames needed to span the whole clip at the selected effort, then
lowers sampling density, object count, or SAM3 batch size only when duration,
resolution, or prior failure makes the workload risky.

## Changed Files

- `src/motionjson/backend/browser_preview.py`
  - Exposes ffprobe-derived `fps`, `sourceFps`, `frameCount`, `bitrate`,
    `byteSize`, and `qualitySource` in browser-preview metadata.
- `src/motionjson/ui/static/ui_selectors.js`
  - Adds duration/resolution/source-FPS-aware scene sweep planning.
  - Adds coverage status, workload risk, total work estimate, video tier,
    duration tier, source frame count, and recommendation reasons.
  - Preserves full-video coverage for normal clips and labels sparse/low-density
    recommendations for long or high-resolution clips.
- `src/motionjson/ui/static/app.js`
  - Passes source FPS/frame count/bitrate/size from selected video metadata into
    adaptive tuning.
  - Persists richer adaptive metadata into run configs.
  - Applies adaptive `maxObjects` and `pointsPerBatch` to SAM3 scene sweep
    config instead of showing one value and submitting another.
- `src/motionjson/ui/static/config_builder.js`
  - Mirrors the richer adaptive metadata and max-object/batch handling in the
    standalone config builder.
- `scripts/test_ui_config_builder.mjs`
  - Adds coverage-first adaptive tests for balanced, high-quality, source-FPS
    clamping, retry, UHD, and long CUDA-backed runs.
- `tests/test_browser_preview.py`
  - Verifies preview probing exposes the metadata used by adaptive tuning.
- `docs/local_ui.md`
  - Documents coverage-first auto tuning and debug-report metadata.
- `docs/design/local-ui-contract.md`
  - Updates the adaptive-parameter contract for video evidence and coverage.

## Tests Run

- `python3 -m py_compile src/motionjson/backend/browser_preview.py`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_browser_preview.py tests/test_local_ui_api.py tests/test_job_lifecycle.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- The UI still cannot know true semantic scene complexity before a model pass.
  It now estimates workload from duration, resolution, source FPS/frame count,
  prior failure, and selected effort, then labels unknown or sparse cases.
- Very long clips may still require segmentation into shorter ranges for good
  object quality. The UI now labels that condition instead of silently sampling
  only the beginning of the video.
- This phase does not change the backend sampler. `maxFrames` still stops after
  the requested number of sampled frames, so the UI avoids front-only sampling by
  lowering `sampleFps` when a long-video frame budget is capped.

## Follow-Up Tasks

- Add backend support for range-based or uniformly distributed sampling when a
  user wants sparse coverage across very long videos.
- Surface the adaptive coverage/workload chips in the run monitor after
  submission, not only in setup/debug metadata.
- Add content-derived complexity scoring after candidate discovery so retries
  can respond to real mask/candidate quality, not only input-video facts.
