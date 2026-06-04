# Phase UI-UX-05 Report: UI Selector Extraction And Context Reduction

## Summary

- Extracted stable dependency-free UI decisions into
  `src/motionjson/ui/static/ui_selectors.js`.
- Kept the static app and existing `MotionJSONUI` facade intact while exposing:
  adaptive parameter summary, project shell state, review/export screen state,
  object discovery defaults, and option help text.
- Updated `app.js` rendering to consume selector outputs for the project drawer,
  post-run guide, and Review/Export screen headings and summaries.
- Added a concise Local UI contract document for future engineers and Codex
  agents.
- Updated the static shell build check and UI tests so the selector module stays
  part of the dependency-free UI contract.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/ui_selectors.js`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_ui_first_run_simplicity.py`
- `docs/design/local-ui-audit.md`
- `docs/design/local-ui-contract.md`
- `docs/design/screenshots/ui-ux-05-before/`
- `docs/design/screenshots/ui-ux-05/`

## Tests Run

- `npm run ui:layout -- --state workflow-goal,prepare-sam3-trace-all-runtime-ready,project-drawer-open,workflow-review,workflow-export,workflow-partial-success --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-05-before`
- `node scripts/test_ui_config_builder.mjs`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py`
- `npm run ui:layout -- --state workflow-goal --viewport desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-05-debug-goal`
- `npm run ui:layout -- --state workflow-goal,prepare-sam3-trace-all-runtime-ready,project-drawer-open,workflow-review,workflow-export,workflow-partial-success --screenshot-dir docs/design/screenshots/ui-ux-05`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03a_local_ui_layout.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- The default all-state screenshot command
  `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-ux-05`
  was attempted, but it did not finish in a practical window after producing
  partial screenshots. The committed after evidence uses the focused Phase 5
  matrix across all configured viewports.
- The Python mock UI shutdown can still emit a resource tracker warning after
  layout captures.
- `app.js` still owns rendering, DOM reads, API calls, and focus transitions.
  Phase UI-UX-05 only extracts mature pure state helpers; broader file splitting
  should wait until more selectors stabilize.

## Follow-Up Tasks

- Extend `ui_selectors.js` only when a decision can be expressed from plain
  snapshots without DOM reads or API calls.
- Keep full default layout captures available for broader visual releases, but
  use targeted state matrices for small selector-only phases when the default
  matrix is too slow.
- Continue reducing `app.js` by moving behavior-preserving, tested selectors
  first, then rendering adapters only when import/loading risk is low.
