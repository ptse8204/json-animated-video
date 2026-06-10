---
historical: true
default_context: false
---

# Phase Report: Review Export State Alignment

## Summary

This phase fixes the Review and Export blocker where the video player could show a moving reviewed trace, but MotionJSON export validation still refused to write JSON.

The root cause was split state ownership. The UI review player treated an explicit `exportIncluded: true` edit as reviewed, while backend export validation still honored stale `review_pending` and `reviewRequired` flags from the original scene artifacts. The selected track could therefore look reviewed in the player but remain non-exportable in `/validate` and `/exports`.

The fix makes a reviewed export-inclusion edit authoritative for moving materialized tracks. Static keyframe fallback output remains blocked by the previous export validation guard.

## Changed Files

- `src/motionjson/backend/corrections.py`
  - Applying `set_export_inclusion` now updates scene, layer, track, metadata, and nested discovery review flags.
  - Review correction state now reports explicitly included tracks as `accepted` instead of leaving them `review_pending`.
- `src/motionjson/backend/export_workflows.py`
  - Export selection now honors explicit reviewed inclusion over stale pending-review flags.
  - Sanitized exported scenes clear review gates for included objects and layers before validation/writing.
- `src/motionjson/ui/server.py`
  - `/api/jobs/{id}/track-edits` now applies export inclusion edits to artifacts instead of only recording correction history.
- `tests/test_local_ui_api.py`
  - Adds the exact regression flow: track selected candidate, confirm export is blocked before review, mark reviewed, validate, and export MotionJSON.
- `tests/test_final_export.py`
  - Covers correction-state inclusion overriding pending review gates while preserving static fallback blocking.

## Tests Run

- `python3 -m py_compile src/motionjson/backend/corrections.py src/motionjson/backend/export_workflows.py src/motionjson/ui/server.py`
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export tests/test_final_export.py::test_review_required_quality_blocks_export_selection tests/test_final_export.py::test_explicit_review_inclusion_overrides_pending_review_gate tests/test_final_export.py::test_export_inclusion_rejects_static_keyframe_fallback_motion tests/test_backend_track_corrections.py::test_local_track_edit_export_inclusion_does_not_hide_track`
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_backend_track_corrections.py tests/test_final_export.py tests/test_discovery_providers.py`
- `python3 -m pytest -q`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- This phase fixes the review-to-export contract. It does not change SAM3 video propagation itself.
- Static keyframe fallback output is still blocked because that path creates a visible trace that does not move with the object.
- Existing jobs with stale review state should be reopened and marked reviewed again, or rerun, so the accepted review state is persisted onto the artifacts.

## Follow-Up Tasks

- Add a visible review badge that distinguishes true SAM/SAM3 propagation from template-match fallback.
- Add a targeted UI message when a track is blocked specifically because it is static fallback output.
