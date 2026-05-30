# Phase UI-MODEL-EXPORT-TRACK-SUMMARY Report

## Summary

This phase fixes the Local UI export blocker where a reviewed moving track could
look export-ready in the review panel while `/api/jobs/{jobId}/validate` still
refused to write MotionJSON with:

```text
No exportable object tracks are included; enable at least one accepted track before export
```

The live Chrome tab showed the split state clearly: the UI reported one moving
track selected for MotionJSON export, but export validation returned one issue
across zero checked documents. The backend export builder was trusting the
stale scene review gate and ignoring the accepted materialized track state in
`track_summary`.

The fix reconciles accepted `track_summary` state during export validation and
export packaging. Accepted materialized tracks may now clear stale
`review_pending` / `reviewRequired` scene gates. Hard rejects, deletes, merges,
explicit export exclusions, failed tracks, raster fallback, and static keyframe
fallback remain blocked.

## Current UI State

- The current UI can reach a successful reviewed export state with ready
  Website package, MotionJSON scene, runtime snippet, Remotion plan, and
  developer handoff cards.
- The live problematic state was caused by backend state ownership, not by the
  export card layout: review metadata showed an accepted moving track while the
  scene graph still carried review-required metadata.
- Rights and attribution warnings are non-blocking and remain visible after a
  valid export.
- Static keyframe fallback diagnostics still surface as warnings/errors and are
  not bypassed by this fix.

## Changed Files

- `src/motionjson/backend/export_workflows.py`
  - Loads the latest materialized `track_summary` during export tree building.
  - Derives export-ready track IDs from accepted/non-excluded tracks.
  - Allows accepted track-summary state to clear stale review gates for matching
    scene objects and layers.
  - Keeps hard exclusion statuses and static keyframe fallback blocking intact.
- `tests/test_final_export.py`
  - Covers accepted track-summary state overriding stale scene review gates.
  - Covers hard scene rejection not being overridden by track summary state.
- `tests/test_local_ui_api.py`
  - Adds a regression for stale scene review metadata plus accepted track
    summary state.
  - Verifies validation succeeds and a debug export with masks enabled writes
    `export_mask` artifacts.

## Browser/Website Validation

- Used the Chrome plugin to claim the live MotionJSON Local UI tab and run the
  page's own `Validate again` action.
- Confirmed the live backend error was `No exportable object tracks are
  included; enable at least one accepted track before export`.
- Started the Local UI in debug mock mode at `http://127.0.0.1:8897/ui/`.
- In Chrome, opened the local UI, switched to Review & export, validated, and
  exported a reviewed moving track.
- Browser smoke reached a ready export handoff state with:
  - Website package: ready
  - MotionJSON scene: ready
  - Runtime snippet: ready
  - Remotion plan: ready
  - Developer handoff bundle: ready
  - Validation: 0 issues across 2 documents
- Browser console warnings observed during smoke were from installed Chrome
  extensions, not the MotionJSON app.

No screenshot set was committed because this phase does not change UI layout,
cards, panels, fonts, or responsive behavior.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/backend/export_workflows.py tests/test_local_ui_api.py tests/test_final_export.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_final_export.py::test_export_ready_track_summary_overrides_stale_scene_review_gate tests/test_final_export.py::test_export_ready_track_summary_does_not_override_hard_rejection tests/test_local_ui_api.py::test_local_ui_exports_accepted_track_summary_with_masks_when_scene_review_gate_is_stale`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_local_ui_api.py::test_local_ui_exports_accepted_track_summary_with_masks_when_scene_review_gate_is_stale tests/test_final_export.py::test_export_ready_track_summary_overrides_stale_scene_review_gate tests/test_final_export.py::test_export_ready_track_summary_does_not_override_hard_rejection`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_final_export.py tests/test_local_ui_api.py tests/test_backend_track_corrections.py` (`58 passed`)
- `npm test` (`21 passed`)
- `npm run build`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` (`539 passed, 1 skipped`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- This does not repair bad tracking. Static keyframe fallback still blocks
  export because it does not prove object motion.
- Existing live Colab/UI jobs may still need the patched server code to be
  redeployed or the job rerun/revalidated before the UI can export.
- The default compact preset does not include raw mask files. Use the debug or
  mask-including export controls when the handoff needs mask artifacts.

## Follow-Up Tasks

- Add a visible badge that distinguishes true SAM3 Tracker Video, template-match
  fallback, and static keyframe fallback.
- Add a UI action that explicitly says "Mark reviewed and validate" when the
  track list is checked but no persisted export-inclusion edit exists.
- Consider surfacing mask inclusion in the primary export card when the selected
  handoff needs raw mask sequences.
- Future agents should keep export source-of-truth changes backend-first: tests
  should cover scene graph, track summary, correction history, static fallback,
  and generated artifact kinds together before adjusting UI copy.
