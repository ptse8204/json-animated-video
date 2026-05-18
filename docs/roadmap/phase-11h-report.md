# Phase 11H Report: Commercial Workspace Mode

## Summary

Phase 11H packages the commercial Local UI into a more cohesive workspace mode.
The local backend now exposes `/api/workspace` and `/api/preferences`, backed by
local SQLite preferences. The response gathers recent projects, recent videos,
recent jobs, guided tasks, provider-settings summary, export presets, and user
preferences without exposing local storage keys or provider secrets.

The Local UI sidebar now includes a Workspace panel with guided task shortcuts,
recent work, and saved defaults for the preferred workflow and export preset.
Mock/no-model remains the safe default, and provider keys continue to live only
in the redacted Provider settings surface.

## Changed Files

- `src/motionjson/backend/db.py`
- `src/motionjson/backend/workspace.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `tests/test_local_ui_api.py`
- `docs/local_ui.md`
- `docs/roadmap/phase-11h-report.md`

## Tests Run

- `python3 -m py_compile src/motionjson/backend/workspace.py src/motionjson/backend/db.py src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_workspace_preferences_and_recent_work_are_public tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public`
  - Result: 2 passed.
- `npm run build`
- `npm run ui:layout -- --state real-empty-shell,real-expanded-shell --viewport laptop-1366,tablet-1024`
  - Result: passed; the command emitted the existing Python multiprocessing
    resource-tracker semaphore warning during mock worker shutdown.
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_phase03a_local_ui_layout.py`
  - Result: 31 passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
- `git diff --check`

## Screenshots And Demos Produced

No new screenshots were produced in this subphase. The workspace panel is
covered by the existing Local UI layout smoke matrix and static shell checks.

## Known Limitations

- Preferences are local UI defaults only; they do not implement multi-user
  account sync.
- The Workspace panel summarizes recent work and guided tasks, but it does not
  replace the detailed project, provider settings, review, or export panels.
- Hosted-provider credentials remain settings-only unless runtime adapters
  explicitly consume them.

## Follow-Up Tasks

- Add a dedicated workspace screenshot in the next docs asset refresh.
- Use the preference defaults to preselect the initial workspace goal on page
  load once the UX has enough user testing.
