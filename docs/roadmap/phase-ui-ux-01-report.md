---
historical: true
default_context: false
---

# Phase UI-UX-01 Report: UX Regression Gates And Baseline Evidence

## Summary

- Captured before/after browser evidence for the guided Local UI UX states:
  `real-empty-shell`, `workflow-goal`, `workflow-video`,
  `prepare-sam3-trace-all-runtime-ready`, `workflow-run-asset-stalled`,
  `workflow-review`, `workflow-export`, and `job-review`.
- Strengthened `npm run ui:layout` so review/export states must show useful
  content, fixed workflow actions must not cover active cards, and export states
  cannot expose multiple primary export actions.
- Repaired the blank `job-review` capture by using the seeded review fixture
  instead of hiding the workspace behind an empty diagnostics rail.
- Moved the guided workflow action bar into normal document flow and demoted the
  duplicate studio header export button.

## Changed Files

- `scripts/check_local_ui_layout.mjs`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/index.html`
- `tests/test_ui_first_run_simplicity.py`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-ux-01-before/`
- `docs/design/screenshots/ui-ux-01/`

## Tests Run

- `npm run ui:layout -- --state real-empty-shell,workflow-goal,workflow-video,prepare-sam3-trace-all-runtime-ready,workflow-run-asset-stalled,workflow-review,workflow-export,job-review --screenshot-dir docs/design/screenshots/ui-ux-01-before`
- `npm run ui:layout -- --state workflow-goal,workflow-review,workflow-export,job-review --viewport mobile-390,desktop-1440 --screenshot-dir /tmp/motionjson-ui-ux-01-check-3`
- `npm run ui:layout -- --state real-empty-shell,workflow-goal,workflow-video,prepare-sam3-trace-all-runtime-ready,workflow-run-asset-stalled,workflow-review,workflow-export,job-review --screenshot-dir docs/design/screenshots/ui-ux-01`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03a_local_ui_layout.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- This phase adds the regression gates and minimal fixes. It does not yet move
  projects into a contextual drawer, add adaptive parameters, or redesign the
  review/export information architecture.
- The export screen still shares much of its content with review; Phase 4 will
  make those screens visually and behaviorally distinct.
- The Python mock UI shutdown still emits an intermittent multiprocessing
  resource tracker warning, but the layout command exits successfully.

## Follow-Up Tasks

- Phase UI-UX-02: replace the persistent project rail with a contextual project
  drawer and add shell selector tests.
- Phase UI-UX-03: add auto-tuned parameter summaries with expert override.
- Phase UI-UX-04: split Review and Export into distinct workspaces and surface
  partial-success recovery clearly.
