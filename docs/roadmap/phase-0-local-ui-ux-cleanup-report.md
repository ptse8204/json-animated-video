# Phase 0 Local UI UX Cleanup Report

## Summary

Phase 0 audited the real Local UI implementation before changing product code.
The current UI is a dependency-light static shell served by the Python local UI:
`index.html` keeps all controls mounted, `app.css` owns the fixed multi-column
layout and responsive breakpoints, and `app.js` is a large stateful browser
module that binds directly to fixed DOM ids.

The cleanup plan is to layer collapsible navigation, diagnostics visibility,
and progressive workflow state over the existing DOM rather than removing or
rebuilding controls. Provider warnings, fallback diagnostics, logs, raw config,
routes, and advanced settings must remain discoverable, with blocking provider
failures summarized outside any closed drawer.

## Changed Files

- `docs/roadmap/phase-0-local-ui-ux-cleanup-report.md`
- `docs/design/screenshots/phase-0-ux-baseline/`

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state real-empty-shell,real-expanded-shell,provider-diagnostics,job-review --viewport mobile-390,tablet-1024,laptop-1366,desktop-1440 --screenshot-dir docs/design/screenshots/phase-0-ux-baseline`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m pytest -q`

The targeted screenshot capture passed. During mock UI shutdown it printed a
Python `resource_tracker` leaked semaphore warning; no layout failures were
reported.

## Browser Evidence

Baseline screenshots were captured for the current dense shell and diagnostic
states at 390x844, 1024x768, 1366x768, and 1440x900:

- `docs/design/screenshots/phase-0-ux-baseline/mobile-390-real-empty-shell.png`
- `docs/design/screenshots/phase-0-ux-baseline/tablet-1024-real-expanded-shell.png`
- `docs/design/screenshots/phase-0-ux-baseline/laptop-1366-provider-diagnostics.png`
- `docs/design/screenshots/phase-0-ux-baseline/desktop-1440-job-review.png`

## Risk Review

A read-only plan-risk scout reviewed the current UI architecture. The risks to
carry forward are:

- Required DOM nodes are statically checked and directly queried by `app.js`;
  workflow steps should hide existing panels rather than unmounting them.
- Sidebar goals and guided goal cards are duplicated; preset state must stay
  synchronized through `applyPreset`.
- Diagnostics and provider failures cannot be hidden without a visible summary
  or blocking status in the main path.
- Collapsed shell states need explicit layout coverage across mobile, tablet,
  laptop, and desktop widths.
- Progressive workflow readiness should reuse existing config/run-plan state
  where possible instead of becoming an independent static step list.

## Known Limitations

- No product code changed in this phase.
- The working tree started with unrelated untracked files:
  `README_UPDATE_NOTES.md`, `apply_motionjson_license_colab_update.py`, and
  `docs/roadmap/phase-license-colab-notebooks-report.md`. They were not touched
  or included.
- Phase 0 screenshots document the baseline problem; they do not represent the
  target guided workflow.

## Follow-Up Tasks

- Phase 1 should add collapsible shell controls without removing required DOM
  ids.
- Phase 2 should replace the static workflow list with a real step controller
  while preserving config, viewer, job, review, correction, timeline, and export
  bindings.
- Layout checks should gain states for collapsed nav, diagnostics open/closed,
  active workflow steps, and show-all panels.
