# Phase 4 Report: Review, Corrections, and Export UX Consolidation

## Summary

Phase 4 consolidated the post-run local UI into a guided sequence across run monitor, candidate review, track review, corrections, and export. The right rail now opens with a compact post-run flow summary for review/correction/export steps, while logs, fallback diagnostics, run defaults, and generated artifacts remain available in collapsed disclosures instead of dominating the default view.

The implementation preserves existing DOM ids and backend route usage for job polling, candidate review, track correction, timeline markers, export validation, artifact browsing, and asset library flows. A read-only review scout found that collapsed diagnostics could hide backend failures; the implementation now auto-opens run logs for failed runs and fallback diagnostics for provider/raster/vector-unavailable diagnostics.

## Changed files

- `src/motionjson/ui/static/index.html`
  - Added the post-run flow guide.
  - Added compact run/review/correction/export status summaries.
  - Moved run defaults, logs/events, fallback diagnostics, and generated artifacts into nested disclosures.
- `src/motionjson/ui/static/app.css`
  - Added post-run guide, summary card, and nested disclosure styles.
- `src/motionjson/ui/static/app.js`
  - Added `postRunWorkflowSummaryFromSnapshot`.
  - Rendered post-run status summaries from existing job, review, correction, diagnostic, and export state.
  - Added automatic surfacing for failed-run logs and fallback/provider diagnostics.
- `scripts/build_ui_shell.mjs`
  - Added static-shell checks for the new post-run ids and affordances.
- `scripts/test_ui_config_builder.mjs`
  - Added unit coverage for post-run summary helper states.
- `scripts/check_local_ui_layout.mjs`
  - Added assertions for post-run guide visibility, summary counts, failure diagnostics, and collapsed artifact defaults.
- `docs/design/screenshots/phase-4-review-export-flow/`
  - Captured before/after screenshot evidence for post-run workflow states.

## Browser evidence

Before and after screenshots were captured under:

- `docs/design/screenshots/phase-4-review-export-flow/before/`
- `docs/design/screenshots/phase-4-review-export-flow/after/`

The before screenshots show review/export work spread across independent right-rail panels. The after screenshots show a guided post-run flow summary with logs, fallback diagnostics, and artifacts collapsed by default while still accessible.

Screenshot matrix covered:

- States: `workflow-review`, `workflow-review-failure`, `workflow-correct`, `workflow-export`, `job-review`, `candidate-review`, `correction-tools`, `export-gate`, `export-handoff`
- Viewports: `mobile-390`, `tablet-768`, `tablet-1024`, `laptop-1366`, `desktop-1440`, `desktop-1920`

## Tests run

- `node --check src/motionjson/ui/static/app.js`
- `node --check scripts/check_local_ui_layout.mjs`
- `npm run build`
- `npm test`
- `npm run lint`
- `npm run embed:smoke`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state workflow-review,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-4-review-export-flow/after`
- `npm run ui:layout -- --state workflow-correct,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-4-review-export-flow/after`
- `npm run ui:layout -- --state job-review,candidate-review,correction-tools,export-gate,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-4-review-export-flow/after`

Validation result: all commands passed after adding the legacy `Artifacts and exports` affordance string required by the existing static-shell guard. The mock UI layout runs still print the existing Python `resource_tracker` leaked semaphore warning at shutdown.

An initial all-in-one Phase 4 layout screenshot command became idle and was stopped; the same state and viewport coverage was rerun successfully in smaller chunks.

## Known limitations

- This phase did not change backend correction/export APIs or extraction behavior.
- Layout evidence uses the repository mock/no-model seeded states, not a GPU/model run.
- Failure logs and fallback/provider diagnostics auto-open when the selected run reports blocking or fallback conditions; non-diagnostic artifacts remain collapsed by default.

## Follow-up tasks

- Keep future review/export additions attached to the post-run summary model rather than adding always-visible right-rail panels.
- Continue Phase 5 with small helper cleanup only where it reduces state/render duplication.
