---
historical: true
default_context: false
---

# Phase 1 Local UI Shell Navigation Report

## Summary

Phase 1 adds collapsible shell navigation without removing existing UI controls
or changing backend/config/rendering behavior. The left navigation can collapse
to a compact rail with the brand mark, active goal, and a menu reopen button.
The diagnostics/right rail is reduced by default and can be opened from a
topbar Details control or closed from the rail header.

Provider and run failures remain visible through the main workspace warning
area and a topbar diagnostics summary. The full diagnostics rail still contains
provider settings, run monitor, logs, review, corrections, exports, asset
library, and routes.

The phase started with unrelated untracked license/Colab files in the working
tree (`README_UPDATE_NOTES.md`, `apply_motionjson_license_colab_update.py`, and
`docs/roadmap/phase-license-colab-notebooks-report.md`). They were not touched
or included in this phase.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `scripts/check_local_ui_layout.mjs`
- `docs/design/screenshots/phase-1-shell-navigation/`
- `docs/roadmap/phase-1-local-ui-shell-navigation-report.md`

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `npm run embed:smoke`
- `python3 -m pytest -q`
- `npm run ui:layout`
- `npm run ui:layout -- --state real-empty-shell,nav-collapsed,diagnostics-open,real-expanded-shell,provider-diagnostics,job-review --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-1-shell-navigation`

The layout commands passed. They emitted the existing mock UI shutdown warnings:
a Python `resource_tracker` leaked semaphore warning, and once a benign
`BrokenPipeError` while Chrome closed a local request during shutdown.

## Browser Evidence

After screenshots were captured under
`docs/design/screenshots/phase-1-shell-navigation/` for:

- 390x844
- 768x1024
- 1024x768
- 1366x768
- 1440x900
- 1920x1080

Representative evidence:

- `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-nav-collapsed.png`
- `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-diagnostics-open.png`
- `docs/design/screenshots/phase-1-shell-navigation/mobile-390-nav-collapsed.png`
- `docs/design/screenshots/phase-1-shell-navigation/tablet-1024-real-expanded-shell.png`

The baseline before evidence remains in
`docs/design/screenshots/phase-0-ux-baseline/`.

## Known Limitations

- This phase does not yet turn the workflow steps into a true controller.
  The center workspace still exposes many cards; Phase 2 owns progressive step
  visibility.
- The right rail is collapsed by default, but diagnostics are still panel-based
  once opened. Phase 4 will consolidate post-run review/correction/export.
- The collapsed sidebar stores state in browser `localStorage`; backend
  preferences were not changed.

## Follow-Up Tasks

- Phase 2 should make the workflow stepper interactive and show one major work
  area at a time by default.
- Phase 3 should simplify central panel copy and keep raw config behind
  disclosure by default.
- Phase 6 should expand keyboard/a11y regression checks around shell toggles
  and active workflow steps.
