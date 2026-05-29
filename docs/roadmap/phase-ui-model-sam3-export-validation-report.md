# Phase Report: SAM3 Export Validation For Moving Tracks

## Summary

This phase fixes the case where SAM3 Scene Sweep could produce a visible trace that did not move with the object and still look export-ready. The root cause was a static keyframe fallback path: when SAM3 video propagation was unavailable or disabled, MotionJSON reused the same keyframe mask across every frame. That output can render a trace, but it cannot follow a moving object.

The implementation now tries a deterministic template-match propagation fallback before accepting a SAM3 Scene Sweep candidate. If that fallback cannot produce moving masks, the static keyframe sequence is marked as rejected before export and old already-produced static fallback artifacts are blocked by export validation before writing MotionJSON.

## Changed Files

- `src/motionjson/providers/discovery.py`
  - Added local template-match mask propagation for SAM3 Scene Sweep fallback.
  - Scene Sweep no longer defaults directly to repeated keyframe masks.
  - SAM3 tracker failures now attempt template fallback before static fallback.
- `src/motionjson/track_filters.py`
  - Added center-motion metrics for object tracks.
  - Added `static_keyframe_mask_sequence` rejection reason and user-facing guidance.
- `src/motionjson/pipeline.py`
  - Applies rejected track-filter decisions to objects and layers before export handoff.
  - Keeps accepted tracks unchanged so existing review gates still work.
- `src/motionjson/backend/export_workflows.py`
  - Detects reviewed static keyframe fallback artifacts during export inclusion.
  - Emits an export validation error explaining that the exported trace would not follow the moving object.
- `tests/test_sam3_providers.py`
  - Covers default SAM3 Scene Sweep template fallback and tracker-failure fallback.
- `tests/test_discovery_providers.py`
  - Covers an end-to-end Scene Sweep pipeline where fallback masks produce moving MotionJSON.
- `tests/test_track_filtering.py`
  - Covers rejection of static keyframe fallback tracks.
- `tests/test_final_export.py`
  - Covers export validation blocking already-reviewed static fallback tracks.

## Tests Run

- `python3 -m py_compile src/motionjson/providers/discovery.py src/motionjson/track_filters.py src/motionjson/pipeline.py src/motionjson/backend/export_workflows.py`
- `python3 -m pytest -q tests/test_sam3_providers.py tests/test_discovery_providers.py tests/test_track_filtering.py tests/test_final_export.py`
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export tests/test_local_ui_api.py::test_local_ui_export_validation_messages_explain_unreviewed_auto_discovery tests/test_quality_engine.py::test_quality_propagates_to_all_core_manifests_and_allows_null_centroid tests/test_schema_validation.py::test_discovery_metadata_validates_across_motionjson_artifacts`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- Template matching is a deterministic fallback, not a replacement for a working SAM3 video propagation runtime. It can fail on occlusion, major appearance changes, large scale changes, or ambiguous backgrounds.
- Static keyframe fallback output is now blocked because it does not prove motion tracking. Users who need to export a truly stationary object should use a tracking path that produces valid per-frame masks or provide external masks.
- Existing failed/static jobs should be rerun so the new fallback and export validation are applied to fresh artifacts.

## Follow-Up Tasks

- Add a UI badge that clearly distinguishes `template_match_fallback` from true SAM3 Tracker Video propagation.
- Add a review-side warning for objects rejected because their mask center never moved.
- Continue investigating the upstream SAM3 Tracker Video runtime issue separately from export validation.
