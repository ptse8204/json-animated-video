---
historical: true
default_context: false
---

# Phase RECOVERY-02 Report - Review Track Classification

## Summary

Implemented a focused review/export truthfulness slice. Review payloads now classify tracks as moving, needs refinement, static fallback, rejected, or diagnostic-only; expose mask-quality fields; and mark static keyframe fallback as blocked/diagnostic before export validation. The UI now shows track quality chips and keeps static fallback from blocking a separate valid moving-track export.

## Changed Files

- `src/motionjson/ui/server.py`
  - Adds review-track enrichment for `trackClass`, `exportEligibility`, `exportBlockReason`, and `maskQuality`.
  - Marks static keyframe fallback tracks as diagnostic-only with `exportIncluded=false`.
  - Carries discovery metadata through object-manifest-derived tracks.
- `src/motionjson/backend/job_lifecycle.py`
  - Excludes blocked/static/diagnostic tracks from exportable track counts.
- `src/motionjson/ui/static/app.js`
  - Treats static fallback as non-exportable for both new and legacy review payloads.
  - Adds user-visible quality chips: `Good outline`, `Needs refinement`, `Static fallback`.
  - Updates export readiness so static fallback is blocked only when it is the only output, and diagnostic when a valid moving track exists.
- `scripts/test_ui_config_builder.mjs`
  - Covers quality chips, static-only repair routing, and mixed moving/static export readiness.
- `tests/test_job_lifecycle.py`
  - Covers lifecycle export counts with mixed moving/static tracks.
- `tests/test_local_ui_api.py`
  - Covers backend review-summary enrichment for moving and static fallback tracks.

## Tests Run

- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_final_export.py tests/test_track_filtering.py tests/test_job_lifecycle.py`
  - Result: passed, 171 tests.
- `npm test`
  - Result: passed, 21 node tests.
- `npm run build`
  - Result: passed.
- `python3 -m motionjson.cli --help`
  - Result: passed.
- `python3 -m motionjson.cli extract --help`
  - Result: passed.
- `git diff --check`
  - Result: passed.

## Known Limitations

- `maskQuality` is a conservative review signal, not a full segmentation-quality model. It uses outline presence, bbox fill ratio, mask-area ratio, confidence, and static fallback detection.
- The review tools still need the later workbench phase for better editing ergonomics and prompt repair flows.
- Candidate-first materialization remains a follow-up; this phase classifies produced tracks rather than changing discovery/materialization order.

## Follow-Up Tasks

- Add candidate-first SAM3 materialization so rejected/background-like candidates never consume expensive raster output.
- Add prompt-repair workflow states for `needs_refinement` and `static_fallback`.
- Rebuild the desktop review workbench with screenshot evidence and no buried tool panels.
