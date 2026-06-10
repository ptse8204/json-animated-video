---
historical: true
default_context: false
---

# Phase 03A Report - Commercial Local UI Redesign

## Summary

Phase 03A replaced the debug-heavy Local UI shell with a commercial product
layout while preserving the existing static UI and local API behavior. The UI
now has a stable left goal rail, main workspace, right inspector, visible
workflow steps, collapsed advanced settings, and progressive disclosure for
jobs, review, artifacts/export, corrections, library, capabilities, and routes.
The review inspector defaults collapsed; the run monitor remains open as the
predictable job/status area.

The controlling commercial roadmap was restored to
`docs/codex/MOTIONJSON_CODEX_FUTURE_PLAN.md`. Repo-local skills were added for
commercial UI, visual regression, and provider-settings security so future
phases have reusable process rules.

The phase started from a dirty tree because the commercial roadmap artifact was
present only as an untracked `_COMMERCIAL.md` file. It was moved into the
canonical path requested by the goal before product code edits.

## Changed Files

- `.agents/skills/motionjson-commercial-ui/SKILL.md`
- `.agents/skills/motionjson-visual-regression/SKILL.md`
- `.agents/skills/motionjson-provider-settings-security/SKILL.md`
- `docs/codex/MOTIONJSON_CODEX_FUTURE_PLAN.md`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `package.json`
- `tests/test_phase03a_local_ui_layout.py`
- `docs/design/local-ui-audit.md`
- `docs/design/local-ui-product-principles.md`
- `docs/design/design-system.md`
- `docs/design/screenshots/baseline/*`
- `docs/design/screenshots/baseline-matrix/*`
- `docs/design/screenshots/phase-03a/*`
- `docs/assets/local-ui-*.png`
- `docs/assets/README_ASSETS.md`
- `docs/local_ui.md`

## UI And Design Improvements

- Added product information architecture around the main local workflow:
  create/open project, add video, choose mode/model, confirm locality, run,
  review candidates, correct tracks, preview, export.
- Moved provider warnings into the extraction settings panel near the affected
  run controls.
- Collapsed advanced parameters by default.
- Grouped right-inspector panels into native disclosure sections:
  Run monitor, Review, Artifacts and exports, Corrections, Asset library, and
  Routes.
- Added design tokens for spacing, radius, z-index, and status colors.
- Added independent desktop scroll containers and responsive breakpoints for
  1366px, 1440px, 1920px, and 1024px checks.
- Preserved the existing vanilla static app, DOM IDs, API calls, and CLI
  compatibility.

## Screenshots And Demos

Baseline screenshots:

- `docs/design/screenshots/baseline/local-ui-first-run.png`
- `docs/design/screenshots/baseline/local-ui-new-project.png`
- `docs/design/screenshots/baseline/local-ui-extraction-wizard.png`
- `docs/design/screenshots/baseline/local-ui-provider-diagnostics.png`
- `docs/design/screenshots/baseline/local-ui-job-review.png`
- `docs/design/screenshots/baseline-matrix/laptop-1366-*.png`
- `docs/design/screenshots/baseline-matrix/desktop-1440-*.png`
- `docs/design/screenshots/baseline-matrix/desktop-1920-*.png`
- `docs/design/screenshots/baseline-matrix/tablet-1024-*.png`

After-redesign viewport screenshots:

- `docs/design/screenshots/phase-03a/laptop-1366-*.png`
- `docs/design/screenshots/phase-03a/desktop-1440-*.png`
- `docs/design/screenshots/phase-03a/desktop-1920-*.png`
- `docs/design/screenshots/phase-03a/tablet-1024-*.png`

README screenshots were regenerated through the real local UI capture path:

- `docs/assets/local-ui-first-run.png`
- `docs/assets/local-ui-new-project.png`
- `docs/assets/local-ui-extraction-wizard.png`
- `docs/assets/local-ui-provider-diagnostics.png`
- `docs/assets/local-ui-job-review.png`

## Validation Run

- `python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/baseline` - passed.
- `git worktree add --detach /tmp/motionjson-phase03a-baseline-worktree HEAD` plus `PYTHONPATH=/tmp/motionjson-phase03a-baseline-worktree/src node /tmp/motionjson-phase03a-baseline-worktree/scripts/check_local_ui_layout.mjs --screenshot-dir docs/design/screenshots/baseline-matrix` - passed and captured the pre-redesign viewport matrix from the detached worktree.
- `npm run build` - passed.
- `python3 -m pytest tests/test_phase13_packaging_onboarding.py::test_local_ui_exposes_first_run_diagnostics_panel tests/test_cli_ui.py::test_ui_command_help_documents_local_launcher -q` - passed, 2 tests.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-03a` - passed for 1366x768, 1440x900, 1920x1080, and 1024x768 across the real empty shell, real seeded shell, real expanded shell, first-run, new-project, extraction-wizard, provider-diagnostics, and job-review states.
- `python3 scripts/capture_docs_assets.py` - passed and regenerated README assets.
- `python3 scripts/capture_docs_assets.py --check` - passed, Chrome available.
- `npm run build && npm test && npm run lint` - passed, 19 Node tests plus runtime lint.
- `python3 -m pytest tests/test_phase03a_local_ui_layout.py tests/test_docs_assets.py tests/test_cli_ui.py tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py tests/test_phase9_ui_job_review_smoke.py -q` - passed, 44 tests.
- `python3 -m pytest -q` - passed, 294 tests.
- `python3 -m motionjson.cli ui --help` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed; reported 22 providers and no-model smoke readiness.
- `npm run ui:layout -- --check` - passed; reports the required viewport/state matrix.

The layout smoke command emits a Python multiprocessing resource-tracker
semaphore warning while shutting down the mock job worker in this environment.
The command exits successfully after the DOM overlap/overflow checks pass.

## Known Limitations

- The UI remains dependency-free static HTML/CSS/JavaScript. This phase did not
  migrate the frontend to React or add a component framework.
- The layout checker uses local Chrome/Chromium. Environments without Chrome can
  still run `npm run ui:layout -- --check` to report that limitation.
- The phase focused on the commercial shell, hierarchy, screenshots, and layout
  validation. Provider key/model settings are Phase 03B.
- Native `details` panels provide disclosure behavior; no custom dialog/menu
  focus trap was added because this phase did not introduce custom modal or menu
  components.

## Review Fixes

The read-only diff-review scout flagged that layout checks originally covered
docs capture modes more than the real shell. The layout script now validates the
real empty shell, real seeded shell, and fully expanded shell before it checks
docs capture states. The scout also flagged default review clutter and an
incomplete workflow strip; the Review inspector now defaults collapsed and the
workflow strip covers the full create/open through export path.

## Follow-Up Tasks

- Phase 03B: add BYOK provider/model settings, secret redaction, readiness
  checks, and cost/privacy warnings in the redesigned settings surface.
- Consider replacing the CSS override block with a cleaned single-pass stylesheet
  once Phase 03B stabilizes the settings UI.
- Add screenshot diff comparison if the project later adopts a browser test
  dependency.
