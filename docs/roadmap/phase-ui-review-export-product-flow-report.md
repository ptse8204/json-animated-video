# Phase Report: Review Export Product Flow

## Summary

- Promoted MotionJSON export from an Advanced-only rail action into the main Review & Export panel.
- Added a visible export checklist for normal users: moving track verified, reviewed for export, MotionJSON validation, and static keyframe fallback status.
- Reused the per-frame review track data used by the overlay player to compute moving-track readiness and to draw a result-mode motion trail.
- Preserved the static keyframe fallback block: fallback tracks are shown as blocked and cannot enable export as MotionJSON motion.
- Updated the layout fixture to show multi-frame red-ball motion, so screenshots and layout checks represent the intended product path.

## Changed Files

- `src/motionjson/ui/static/index.html`
  - Adds main-panel export checklist and visible `Export MotionJSON` / `Validate export` actions.
  - Keeps Advanced export settings separate from the normal export path.
- `src/motionjson/ui/static/app.js`
  - Adds moving-track metrics and static-keyframe fallback detection.
  - Renders review rows as `Reviewed moving track` when per-frame motion is verified.
  - Blocks static fallback export actions before users write MotionJSON.
  - Draws a dashed motion trail in result-mode overlay previews.
  - Updates capture fixtures with multi-frame red-ball motion.
- `src/motionjson/ui/static/app.css`
  - Styles the main export checklist, visible export buttons, and responsive checklist layout.
- `scripts/test_ui_config_builder.mjs`
  - Adds regression coverage for moving-track detection, static fallback blocking, and export readiness rows.
- `docs/design/screenshots/phase-ui-review-export-product-flow/`
  - Captured evidence for `workflow-review`, `workflow-export`, `export-gate`, and `export-success` across supported viewports.

## Tests Run

- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-ui-review-export-product-flow --state workflow-review,workflow-export,export-gate,export-success --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `python3 -m pytest -q tests/test_final_export.py tests/test_backend_track_corrections.py tests/test_phase03a_local_ui_layout.py tests/test_phase9_ui_job_review_smoke.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m pytest -q`
- `git diff --check`

## Screenshot Evidence

- Saved 26 PNG screenshots under `docs/design/screenshots/phase-ui-review-export-product-flow/`.
- The 1440px workflow export screenshot shows the main review panel with:
  - `Export checklist`;
  - `Moving track verified`;
  - `Reviewed for export`;
  - `MotionJSON validation needed`;
  - `Static keyframe fallback not used`;
  - visible `Validate export` and `Export MotionJSON` buttons.

## Known Limitations

- This phase improves the review/export product path and client-side visibility. It does not change SAM3 model loading or CUDA runtime behavior.
- The overlay motion trail depends on sampled review track frames. If a backend provider only returns one frame, the UI correctly reports motion as not verified.
- The full Python suite passed with one pre-existing skipped test.

## Follow-Up Tasks

- Use a real SAM3 Scene Sweep run artifact to compare the UI motion trail against dense backend tracks after the next GPU runtime fix.
- Consider making the selected object list collapsible when many candidates are present, so the export checklist stays first-screen visible with very large review sets.
