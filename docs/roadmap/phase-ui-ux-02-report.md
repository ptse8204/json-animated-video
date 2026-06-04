# Phase UI-UX-02 Report: Contextual Project Drawer

## Summary

- Replaced the default left project rail with a topbar project button and an
  off-canvas project drawer.
- Kept the existing project list, new project action, workspace preferences,
  Local API status, and capabilities inside the drawer.
- Default first-run and guided workflow states now use a full-width workspace
  instead of reserving a project column.
- Added layout coverage for the explicit `project-drawer-open` state and
  default-closed project drawer assertions.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `tests/test_ui_first_run_simplicity.py`
- `tests/test_phase03a_local_ui_layout.py`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-ux-02-before/`
- `docs/design/screenshots/ui-ux-02/`

## Tests Run

- `npm run ui:layout -- --state real-empty-shell,workflow-goal,workflow-video,nav-collapsed,diagnostics-open --screenshot-dir docs/design/screenshots/ui-ux-02-before`
- `npm run ui:layout -- --state real-empty-shell,workflow-goal,project-drawer-open,workflow-video --viewport mobile-390,desktop-1440 --screenshot-dir /tmp/motionjson-ui-ux-02-check-2`
- `npm run ui:layout -- --state real-empty-shell,workflow-goal,workflow-video,project-drawer-open,nav-collapsed,diagnostics-open --screenshot-dir docs/design/screenshots/ui-ux-02`
- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03a_local_ui_layout.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- The drawer reuses the existing project rail visual design. This phase changes
  placement and interaction, not the deeper information architecture of project
  history.
- The drawer overlay has a shadow but no separate backdrop; this keeps the
  static implementation small while preserving keyboard close behavior.
- The Python mock UI shutdown can still emit a resource tracker warning after
  layout captures.

## Follow-Up Tasks

- Phase UI-UX-03: add adaptive parameter summaries with expert override.
- Phase UI-UX-04: make Review and Export distinct workspaces.
- Phase UI-UX-05: extract mature shell state selectors into dedicated UI helper
  modules.
