---
historical: true
default_context: false
---

# Phase Flow Rebuild 4 Report

## Summary

- Added pure frontend selectors for normalized job lifecycle rows, Job Center
  state, and review gates.
- Updated Job Center rendering to prefer backend `job.lifecycle` data when it is
  present, while preserving legacy job fields for compatibility.
- Changed selected-job fallback behavior so the newest active job is selected by
  default, while an explicitly selected recent/failed job remains selected.
- Kept failed and canceled jobs visible/selectable and preserved raster/vector
  diagnostic reason strings in job rows.
- Added JS fixture coverage for no-job, queued, running, failed, canceled,
  backend-shaped lifecycle provider fields, candidate-ready, track-ready,
  raster-diagnostic, and export-ready states.
- Ran a read-only diff-review scout before commit; it found lifecycle contract
  mismatches for provider labels, review counts, and cancellation affordances.
  Those issues were fixed before this report was committed.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_config_builder.mjs`
- `docs/roadmap/phase-flow-rebuild-4-report.md`

## Tests Run

- `npm test`
- `npm run build`
- `npm run ui:layout -- --check --state workflow-run,workflow-review,workflow-review-failure,job-review --viewport mobile-390,tablet-1024,laptop-1366,desktop-1440`
- `npm run ui:layout -- --state workflow-run,workflow-review,workflow-review-failure,job-review --viewport mobile-390,tablet-1024,laptop-1366,desktop-1440`
- Read-only diff-review scout for the final Phase 4 selector diff.

The first `ui:layout --check` command only reported browser availability and did
not run assertions, so the second command is the effective browser smoke.

## Browser Evidence

No new screenshot set was committed for this phase because the changes are
selector and rendering-state logic, not layout or visual hierarchy changes.
The browser smoke rendered the affected run monitor, normal review, failed
review, and job-review states across `390x844`, `1024x768`, `1366x768`, and
`1440x900` and passed.

## Known Limitations

- Retry remains intentionally absent until a safe retry policy is implemented.
- Some workflow and export gate logic is still split between existing selectors
  and rendering functions; this phase moved the Job Center and review gate
  foundation without rewriting every caller.
- Polling remains on the existing refresh loop; the new selector makes selected
  job fallback deterministic but does not replace polling.

## Follow-Up Tasks

- Phase 5 should wire candidate tracking and export gates into the same selector
  style.
- A future cleanup can move the remaining primary-action and export-gate
  derivation out of DOM-derived status classes.
