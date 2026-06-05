# Phase Recovery 03 Report: Desktop Review Workbench

## Summary

Started from a clean working tree after `phase recovery-02: classify review tracks for export`.

This phase repairs the desktop review/export surface so a completed run has a usable first-screen workbench instead of scattering review state across a narrow rail and below-fold panels. The review screen now keeps the video preview, object list, selected-object diagnostics, runtime proof, export eligibility, and review tool readiness visible in one bounded desktop layout. The export screen is now a separate package-readiness workspace with review tools alongside the export checklist.

The layout regression gate was strengthened so review/export can no longer pass merely because content is nonblank. It now checks that desktop review exposes the selected-object diagnostics/runtime proof, actual review-tool cards, and bounded preview/list/inspector/tool regions inside the visible workbench.

## Changed Files

- `src/motionjson/ui/static/index.html`
  - Added `studioTrackInspector` for selected-object diagnostics and runtime proof inside the main review workbench.
- `src/motionjson/ui/static/app.js`
  - Mirrors selected-track detail into the new workbench inspector.
  - Renders run-level runtime proof/readiness/artifact/object facts in the review workbench.
  - Removes stale `new-project` capture inline shell columns that conflicted with the current project drawer model.
- `src/motionjson/ui/static/app.css`
  - Adds desktop-first result-mode workbench layout.
  - Collapses the external diagnostics rail during normal result mode because the review workbench now owns selected object/runtime/export state.
  - Binds the workbench height to the remaining viewport so preview, object list, inspector, and tools stay above the fold on 1366x768, 1440x900, and 1920x1080.
  - Allows the project button to wrap rather than clipping real project names.
- `scripts/check_local_ui_layout.mjs`
  - Adds desktop assertions for visible review inspector, runtime proof, review-tool cards, and bounded workbench regions.
  - Adds export workbench bound checks.
- `docs/design/screenshots/recovery-03-before/`
  - Focused before evidence for review/export/job-review desktop states.
- `docs/design/screenshots/recovery-03-after/`
  - Focused after evidence for review/export/job-review desktop states.
- `docs/design/screenshots/recovery-03-after-new-project/`
  - Targeted evidence for the `new-project` shell regression after fixing stale capture layout.
- `docs/design/screenshots/recovery-03/`
  - Full layout matrix screenshot evidence after final fixes.

## Tests Run

- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_final_export.py tests/test_track_filtering.py tests/test_job_lifecycle.py`
  - `171 passed`
- `npm test`
  - `21 passed`
- `npm run build`
  - passed
- `npm run ui:layout -- --state workflow-review,workflow-export,job-review --viewport laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/recovery-03-before`
  - passed baseline capture before edits
- `npm run ui:layout -- --state workflow-review,workflow-export,job-review --viewport laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/recovery-03-after`
  - passed after workbench edits
- `npm run ui:layout -- --state new-project --viewport tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/recovery-03-after-new-project`
  - passed after fixing the stale `new-project` capture shell layout
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/recovery-03`
  - passed full matrix across `mobile-390`, `tablet-768`, `tablet-1024`, `laptop-1366`, `desktop-1440`, and `desktop-1920`
- `python3 -m motionjson.cli --help`
  - passed
- `python3 -m motionjson.cli extract --help`
  - passed
- `python3 -m motionjson.cli backend --help`
  - passed during validation
- `git diff --check`
  - passed

## Known Limitations

- The desktop workbench is now bounded and usable, but the review list is intentionally scrollable on 1366x768 because the workflow still shows the post-run status strip and top guided CTA. A later UX pass should decide whether the post-run strip can collapse after the user reaches review.
- The embedded Canvas player remains represented as ready tool cards in the bounded review workbench; the large iframe is hidden in normal review mode to avoid burying controls. A later phase should implement a proper bottom drawer/modal for the embedded tool.
- This phase does not improve SAM mask quality or tracker behavior. It makes review state usable after the backend/review-state fixes from the prior phases.

## Follow-Up Tasks

- Add a real review-tool drawer/modal for Canvas player, object selection, and timeline editor.
- Collapse or pin the post-run flow summary once the user is actively reviewing objects.
- Continue separating review actions from export validation so “Validate reviewed objects” and “Export MotionJSON” never feel like the same step.
- Add a visual regression check for at least two visible object rows in the desktop review list when enough tracks exist.
