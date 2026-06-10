---
historical: true
default_context: false
---

# Phase 2 Guided Workflow Stepper Report

## Summary

Phase 2 turns the Local UI workflow labels into an interactive controller. The
default workspace now shows the active step's major work area instead of every
setup, viewer, config, review, correction, and export panel at once.

The controller includes Back/Next navigation, clickable step buttons, per-step
readiness status, and a Show all panels escape hatch for debugging and power
users. Existing DOM nodes remain mounted; inactive workflow panels and fragments
are hidden with `hidden`, `aria-hidden`, and `inert` so they are not left in the
keyboard path. Backend routes, config generation, provider warnings, canvas
prompt drawing, job polling, candidate review, correction tools, timeline
markers, exports, and static serving constraints were preserved.

Read-only review found three Phase 2 issues before commit. The final diff fixes
them by mirroring provider/config/run failures into a visible Run-step alert,
requiring a registered local video before the Video step can advance, and
treating provider-ready text as ready rather than warning state.

The phase started with unrelated untracked license/Colab files in the working
tree (`README_UPDATE_NOTES.md`, `apply_motionjson_license_colab_update.py`, and
`docs/roadmap/phase-license-colab-notebooks-report.md`). They were not touched
or included in this phase.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `docs/design/screenshots/phase-2-guided-workflow/`
- `docs/roadmap/phase-2-guided-workflow-stepper-report.md`

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `node --check scripts/check_local_ui_layout.mjs`
- `npm run build`
- `npm test`
- `npm run lint`
- `npm run embed:smoke`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m pytest -q`
- `npm run ui:layout -- --state workflow-goal,workflow-project,workflow-video,workflow-provider,workflow-prompts,workflow-run,workflow-review,workflow-correct,workflow-export,workflow-dashboard --viewport mobile-390,tablet-768,laptop-1366,desktop-1440`
- `npm run ui:layout -- --state real-empty-shell,workflow-goal,workflow-project,workflow-video,workflow-provider,workflow-prompts,workflow-run,workflow-review,workflow-correct,workflow-export,workflow-dashboard --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-2-guided-workflow`
- `npm run ui:layout`

The layout commands passed. They emitted the existing mock UI shutdown warning
from Python's `resource_tracker` about one leaked semaphore object.

## Browser Evidence

After screenshots were captured under
`docs/design/screenshots/phase-2-guided-workflow/` for:

- 390x844
- 768x1024
- 1024x768
- 1366x768
- 1440x900
- 1920x1080

Representative evidence:

- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-goal.png`
- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-project.png`
- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-video.png`
- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-run.png`
- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-review.png`
- `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-dashboard.png`
- `docs/design/screenshots/phase-2-guided-workflow/mobile-390-workflow-goal.png`

Baseline before evidence remains in
`docs/design/screenshots/phase-0-ux-baseline/` and the Phase 1 shell evidence
remains in `docs/design/screenshots/phase-1-shell-navigation/`.

## Before/After Comparison

| Area | Before evidence | After evidence | Outcome |
| --- | --- | --- | --- |
| Default shell | `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-real-empty-shell.png` | `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-goal.png` | The central workspace starts with goal selection and a real workflow controller instead of the full setup/settings/config grid. |
| Project and video | `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-real-empty-shell.png` | `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-project.png` and `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-video.png` | Project creation and video registration are separate guided steps; the video step remains incomplete until a registered local video exists. |
| Run validation | `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-real-empty-shell.png` | `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-run.png` | Run validation has a visible alert in the active Run step, so provider/config/job failures are not hidden in the provider settings panel. |
| Review/debug | `docs/design/screenshots/phase-1-shell-navigation/desktop-1440-diagnostics-open.png` | `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-review.png` and `docs/design/screenshots/phase-2-guided-workflow/desktop-1440-workflow-dashboard.png` | Review can focus the relevant rail content while Show all panels still restores the advanced dashboard view. |

## Known Limitations

- The setup panel heading still says "Project and video" in both the project
  and video steps. Phase 3 owns copy simplification and step-specific summary
  cards.
- Provider settings, run monitor, review, correction, and export still use the
  existing rail content. Phase 4 will consolidate post-run review/correction
  and export UX more deeply.
- The Next button intentionally blocks advancement when a step lacks required
  state, but step buttons remain clickable for inspection and recovery.

## Follow-Up Tasks

- Phase 3 should simplify panel copy, demote raw config/debug actions, and add
  compact completed-step summaries.
- Phase 4 should make post-run review, corrections, and export feel like one
  guided sequence instead of separate rail sections.
- Phase 6 should add deeper keyboard/a11y checks around workflow navigation and
  focus movement.
