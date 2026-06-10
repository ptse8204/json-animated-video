---
historical: true
default_context: false
---

# Phase 5 Report: Local UI Workflow Helper Refactor

## Summary

Phase 5 kept the static Local UI architecture intact and made a small maintainability cleanup after the guided workflow changes. Repeated status-card markup is now rendered through one helper, and the diagnostic-attention rule that decides when failure/fallback details must surface is exported and covered by tests.

No backend routes, run config generation, correction APIs, export behavior, or provider setup behavior changed.

## Changed files

- `src/motionjson/ui/static/app.js`
  - Added `statusCardMarkup` for workflow summaries, post-run stage cards, and rail status summaries.
  - Exported `diagnosticNeedsImmediateAttention` so failure/fallback surfacing logic is testable.
- `scripts/test_ui_config_builder.mjs`
  - Added unit checks for bad diagnostics, fallback/raster diagnostics, ordinary warnings, and ready diagnostics.
- `scripts/build_ui_shell.mjs`
  - Added static-shell affordance checks for the refactored helpers.

## Tests run

- `node --check src/motionjson/ui/static/app.js`
- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q`
- `npm run ui:layout -- --state workflow-review,workflow-review-failure,workflow-export --viewport mobile-390,tablet-1024,desktop-1440 --screenshot-dir docs/design/screenshots/phase-5-helper-refactor`

Validation result: all commands passed. The targeted layout run printed the existing Python `resource_tracker` leaked semaphore warning at mock UI shutdown.

## Browser evidence

The targeted layout smoke captured review, failure-review, and export states across mobile, tablet, and desktop during validation. Those screenshots were not committed because this phase refactored rendering helpers without intended visual changes.

## Known limitations

- This phase did not split `app.js` into modules because the current static browser build depends on the single-file public helper API.
- The helper cleanup is intentionally narrow; broader state/render decomposition remains future work.

## Follow-up tasks

- Keep new workflow or rail summaries on `statusCardMarkup` rather than adding one-off card templates.
- Consider moving public helper tests into smaller files if `scripts/test_ui_config_builder.mjs` continues to grow.
