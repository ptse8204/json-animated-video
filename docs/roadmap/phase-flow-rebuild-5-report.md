---
historical: true
default_context: false
---

# Phase Flow Rebuild 5 Report

## Summary

- Reworked the post-run review selector around the explicit sequence:
  candidates, track selected, tracks, corrections, export.
- Changed the review-screen primary action to follow the next safe gate:
  keep candidates, track selected candidates, mark tracks for export, open
  diagnostics, or export reviewed objects.
- Kept candidate-only review states candidate-only in layout fixtures so the UI
  no longer masks missing tracks with demo review rows.
- Updated `track-selected` handling to refresh project/job lifecycle state after
  the API returns so the Job Center and selected review data stay synchronized.
- Tightened export disabled reasons for no completed run, active/failed jobs,
  no tracks, pending materialized assets, no reviewed track, and validation
  failures.
- Updated Local UI docs to describe the actual candidate-to-track review flow.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/test_ui_config_builder.mjs`
- `docs/local_ui.md`
- `docs/design/screenshots/flow-rebuild-phase-5/before/`
- `docs/design/screenshots/flow-rebuild-phase-5/after/`
- `docs/roadmap/phase-flow-rebuild-5-report.md`

`docs/codex/codex_ui_flow_rebuild_prompt.md` remains untracked user-supplied
goal context and was intentionally left out of this phase commit.

## Tests Run

- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_backend_api_product.py tests/test_backend_track_corrections.py tests/test_job_lifecycle.py tests/test_candidate_review.py`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/flow-rebuild-phase-5/before --state workflow-review,workflow-review-failure,candidate-review,correction-tools,export-gate,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --state workflow-review --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/flow-rebuild-phase-5/after --state workflow-review,workflow-review-failure,candidate-review,correction-tools,export-gate,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`

## Browser Evidence

- Before and after screenshots were captured under
  `docs/design/screenshots/flow-rebuild-phase-5/`.
- Required viewports checked: `390x844`, `768x1024`, `1024x768`,
  `1366x768`, `1440x900`, and `1920x1080`.
- States checked: normal review, failed review, candidate-only review,
  correction tools, export gate, and export handoff.
- The first after capture failed because the ready review CTA no longer matched
  the expected `Export reviewed objects` label. The CTA label was corrected and
  the focused plus full matrix checks then passed.

## Known Limitations

- `mark reviewed` uses the existing correction API path to include materialized
  tracks for export; there is still no separate backend endpoint named
  `mark-reviewed`.
- The candidate browser remains in the details rail, but candidate-only review
  automatically opens that rail and the main post-run flow now shows the exact
  candidate-to-track gate.
- Retry remains absent until a safe retry policy is defined.

## Follow-Up Tasks

- Phase 6 should update onboarding/docs/notebooks to match the final rebuilt UI
  and include current screenshots where appropriate.
- A future cleanup can move the remaining review rendering helpers into a
  separate static module if the no-build UI packaging stays stable.
