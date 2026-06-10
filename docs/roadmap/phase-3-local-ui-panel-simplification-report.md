---
historical: true
default_context: false
---

# Phase 3 Local UI Panel Simplification Report

## Summary

Phase 3 simplifies the guided Local UI steps without changing backend routes,
config generation, preview drawing, job polling, review, correction, timeline,
or export behavior.

The Project and Video steps now present separate action-oriented setup cards.
The Video step promotes the registered local video path as the primary backend
run input, while browser preview is available as an optional drawing aid. The
Provider and Prompt steps use the existing wizard controls, but visible fields
are now scoped to the active workflow step. The Run step promotes `Start mock
job`, `Validate plan`, and `Start provider run`, while save/load config and raw
generated JSON are collapsed by default.

The workflow controller now renders compact prior-step summary cards so users
can see what they already chose without keeping earlier full forms on screen.
The optional model-plan panel remains available, but it no longer appears above
the primary run controls in the normal Run step.

The phase started with the same unrelated untracked license/Colab files in the
working tree (`README_UPDATE_NOTES.md`,
`apply_motionjson_license_colab_update.py`, and
`docs/roadmap/phase-license-colab-notebooks-report.md`). They were not touched
or included in this phase.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `docs/design/screenshots/phase-3-panel-simplification/`
- `docs/roadmap/phase-3-local-ui-panel-simplification-report.md`

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
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state workflow-goal,workflow-project,workflow-video,workflow-provider,workflow-prompts,workflow-run,workflow-review,workflow-export,workflow-dashboard --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-3-panel-simplification/after`
- `npm run ui:layout -- --state real-empty-shell,real-seeded-shell,real-expanded-shell,extraction-wizard,provider-settings,job-review,candidate-review,correction-tools,export-gate,export-handoff,export-success,copyable-snippet --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --state model-setup,model-setup-local,model-setup-hosted-warning,model-setup-missing,model-setup-invalid,model-setup-success,model-plan-preview,model-plan-warning,model-plan-confirmation,model-plan-queued,model-plan-running,model-plan-succeeded --viewport mobile-390,tablet-1024,desktop-1440`
- `npm run ui:layout -- --state nav-collapsed,diagnostics-open,first-run,new-project,advanced-config,provider-diagnostics --viewport mobile-390,tablet-1024,desktop-1440`

An attempted single unchunked `npm run ui:layout` run stayed idle after more
than twelve minutes and was stopped. The same relevant state coverage was then
run in smaller chunks and passed. The layout commands emitted the existing mock
UI shutdown warning from Python's `resource_tracker` about one leaked semaphore
object.

## Browser Evidence

Before and after screenshots were captured under:

- `docs/design/screenshots/phase-3-panel-simplification/before/`
- `docs/design/screenshots/phase-3-panel-simplification/after/`

Each set covers:

- 390x844
- 768x1024
- 1024x768
- 1366x768
- 1440x900
- 1920x1080

Representative evidence:

- `docs/design/screenshots/phase-3-panel-simplification/before/desktop-1440-workflow-video.png`
- `docs/design/screenshots/phase-3-panel-simplification/after/desktop-1440-workflow-video.png`
- `docs/design/screenshots/phase-3-panel-simplification/before/desktop-1440-workflow-run.png`
- `docs/design/screenshots/phase-3-panel-simplification/after/desktop-1440-workflow-run.png`
- `docs/design/screenshots/phase-3-panel-simplification/after/desktop-1440-workflow-provider.png`
- `docs/design/screenshots/phase-3-panel-simplification/after/desktop-1440-workflow-prompts.png`

## Before/After Comparison

| Area | Before | After | Outcome |
| --- | --- | --- | --- |
| Project setup | Project and video shared one generic card heading. | Project step says "Create or open a project" and promotes `Create project`. | Users see one local workspace action instead of mixed project/video setup. |
| Video setup | Browser preview and advanced local path registration competed for attention. | Registered local path is the primary Video step action; browser preview is optional. | The backend-run requirement is clearer while browser drawing still works. |
| Provider/prompt settings | Provider, object labels, prompt-specific fields, device, and advanced settings were visible together. | Provider step shows provider/mode controls; Prompt step shows object/prompt fields and prompt list. | Users see fewer implementation controls per step. |
| Run step | Optional model-plan controls appeared before the run controls. | `Start mock job`, validation, and provider-run actions appear first; model planning follows. | The safe no-model path and next run action are easier to find. |
| Raw/debug config | Save/load config and raw JSON sat next to run actions. | Save/load and raw generated JSON are collapsed disclosures. | Technical details remain available without dominating the default Run step. |

## Known Limitations

- On narrow mobile viewports, the workflow stepper remains tall. The primary
  step action is available by scrolling; Phase 6 owns deeper responsive and
  keyboard polish.
- The post-run rail still uses separate Review, Corrections, and Export
  sections. Phase 4 owns the deeper review/correction/export consolidation.
- The all-state layout command was validated in chunks after a single
  unchunked run became idle.

## Follow-Up Tasks

- Phase 4 should consolidate run monitor, candidate review, track correction,
  and export into a clearer post-run sequence.
- Phase 5 should keep any new workflow summary/context helpers small and
  stable.
- Phase 6 should add keyboard and responsive checks for summary cards and
  mobile workflow navigation.
