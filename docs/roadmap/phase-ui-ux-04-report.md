---
historical: true
default_context: false
---

# Phase UI-UX-04 Report: Review And Export Workspace Repair

## Summary

- Split the `review_export` workflow step into a small Review/Export substate
  without adding a route or framework.
- Review mode now focuses on object rows, keep/export controls, quality status,
  corrections, and partial-result diagnostics.
- Export mode now focuses on package readiness, included objects, rights notes,
  validation state, and handoff/review tools.
- The guided footer now shows one primary action per mode:
  `Validate reviewed objects` or `Continue to export` in Review, and
  `Validate export` or `Export MotionJSON` in Export.
- Failed jobs with registered partial objects now route to review instead of
  only retry, and the UI shows the failed object/frame diagnostic.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_ui_first_run_simplicity.py`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-ux-04-before/`
- `docs/design/screenshots/ui-ux-04/`

## Tests Run

- `npm run ui:layout -- --state workflow-review,workflow-export,job-review --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-04-before`
- `node scripts/test_ui_config_builder.mjs`
- `npm run ui:layout -- --state workflow-review,workflow-export,workflow-partial-success,job-review --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-04-check`
- `npm run ui:layout -- --state workflow-review,workflow-export,workflow-partial-success,job-review --screenshot-dir docs/design/screenshots/ui-ux-04`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03a_local_ui_layout.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- The Review/Export split is still implemented inside `app.js`; Phase UI-UX-05
  should extract the mature pure selectors and help contracts into small static
  modules.
- The export package screen uses the existing rights metadata if present and
  falls back to a generic source-rights reminder when the fixture or backend
  provides object-shaped copy.
- The Python mock UI shutdown can still emit a resource tracker warning after
  layout captures.

## Follow-Up Tasks

- Phase UI-UX-05: extract UI selectors, adaptive defaults, and help copy into
  dedicated dependency-free modules.
- Add backend-fed failed-object metadata to real partial-success API payloads
  wherever it is missing so the UI can show exact object/frame details outside
  fixtures.
