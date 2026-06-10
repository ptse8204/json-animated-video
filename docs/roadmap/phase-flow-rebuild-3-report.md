---
historical: true
default_context: false
---

# Phase Flow Rebuild 3 Report

## Summary

- Rebuilt the visible Local UI flow around one top-level model:
  `Start -> Video -> Model -> Prepare and run -> Review and export`.
- Removed the default duplicate/noisy task picker by keeping five normal tasks
  visible and moving expert variants behind `Advanced tasks`.
- Added a main-workspace Job Center that shows run status, selected job facts,
  job list, progress, artifacts, and cancel state from existing job data.
- Kept logs, route details, artifacts, provider internals, and correction
  history in the right details rail. Failed runs now open the rail and expose
  logs plus fallback diagnostics.
- Updated guided primary-action behavior so active runs show Run monitor,
  failed/canceled runs expose `Open logs`, and completed review flows keep
  `Export reviewed objects`.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `docs/local_ui.md`
- `docs/design/screenshots/flow-rebuild-phase-3/before/`
- `docs/design/screenshots/flow-rebuild-phase-3/after/`
- `docs/roadmap/phase-flow-rebuild-3-report.md`

## Tests Run

- `npm run build`
- `npm test`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/flow-rebuild-phase-3/before --state workflow-goal,workflow-video,workflow-provider,workflow-run,workflow-review,workflow-review-failure,export-gate --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/flow-rebuild-phase-3/after --state workflow-goal,workflow-video,workflow-provider,workflow-run,workflow-review,workflow-review-failure,export-gate --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`

## Browser Evidence

- Baseline screenshots are in
  `docs/design/screenshots/flow-rebuild-phase-3/before/`.
- Updated screenshots are in
  `docs/design/screenshots/flow-rebuild-phase-3/after/`.
- Baseline layout check reproduced the known failures:
  - `workflow-run` showed a blocked footer reason while a run CTA should be
    available.
  - `workflow-review-failure` did not expose the guided post-run/log/fallback
    diagnostics path.
- After the Phase 3 changes, the same state and viewport matrix passed across
  `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.

## Known Limitations

- The new Job Center reuses existing frontend job data and selected-job facts;
  Phase 4 should move more of this rendering onto pure selectors backed by the
  Phase 1 lifecycle contract.
- Retry remains a future explicit action. Failed runs now expose logs and
  diagnostics, but this phase does not add safe retry policy.
- The right rail still contains the detailed review/correction/export tools;
  this phase makes the normal path clearer without removing advanced tools.

## Follow-Up Tasks

- Phase 4 should centralize frontend workflow gates, primary actions, job-center
  derivation, failure summaries, review gates, and export gates in pure
  selectors.
- Phase 5 should make the post-run sequence `Candidates -> Track selected ->
  Tracks -> Corrections -> Export` more explicit in the main review workspace.
