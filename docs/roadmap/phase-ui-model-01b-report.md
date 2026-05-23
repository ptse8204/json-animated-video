# Phase UI-MODEL-01B Report - First-Run Notebook Unblock

## Summary

UI-MODEL-01B fixes the Local UI first-run path that was leaving notebook users
stuck at the opening goal screen or restoring them into later review/export
steps from stale browser storage.

The phase does three things:

- clamps restored workflow state back to the earliest valid setup step when a
  new backend session has no matching project/video/job state;
- replaces the misleading step-1 `Validate plan` primary action with explicit
  first-run actions: `Continue to project setup` and `Start with demo video`;
- reduces mock-centric startup copy when debug mock mode is not actually active.

The working tree was clean at phase start.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_config_builder.mjs`
- `docs/design/screenshots/phase-ui-model-01b/*`
- `docs/roadmap/phase-ui-model-01b-report.md`

## Browser Evidence

Before screenshots were captured from detached commit `7e5387f` with
`PYTHONPATH=src` so the browser run used the previous source tree instead of the
editable install:

```text
docs/design/screenshots/phase-ui-model-01b/before
```

After screenshots were captured from the current workspace:

```text
docs/design/screenshots/phase-ui-model-01b/after
```

Required viewports covered:

- `390x844`
- `768x1024`
- `1024x768`
- `1366x768`
- `1440x900`
- `1920x1080`

States covered:

- `first-run`
- `workflow-project`
- `workflow-video`

Representative comparison:

- Before: `before/desktop-1440-first-run.png` shows the old
  `Choose video preview` plus `Validate plan` dead-end CTA.
- After: `after/desktop-1440-first-run.png` shows the simplified
  `Continue to project setup` plus `Start with demo video` path.

## Implementation Notes

- Added `workflowRestoredStepFromSnapshot()` so stale localStorage workflow
  state cannot reopen an empty notebook session on review/export screens.
- Added `reconcileWorkflowProgress()` during startup refresh so empty sessions
  also reset `Show all panels` to the guided view.
- Added a one-click bundled demo-video path that creates a starter project,
  registers `examples/demo_red_ball.mp4`, loads the preview, and advances to
  Model Connections.
- Auto-advance now moves project creation to the video step and video
  registration to the provider step.
- Updated first-run copy so non-debug startup says `Local first` instead of
  implying the app is already in mock mode.

## Tests Run

```bash
npm run build
```

Passed.

```bash
npm test
```

Passed: 21 Node tests.

```bash
npm run lint
```

Passed.

```bash
git diff --check
```

Passed.

```bash
node scripts/check_local_ui_layout.mjs --state first-run,workflow-project,workflow-video --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-ui-model-01b/after
```

Passed.

```bash
PYTHONPATH=src node scripts/check_local_ui_layout.mjs --state first-run,workflow-project,workflow-video --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir /Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/phase-ui-model-01b/before
```

Passed from detached commit `7e5387f`.

## Known Limitations

- The bundled demo shortcut assumes `examples/demo_red_ball.mp4` is present in
  the runtime working directory. If a downstream install omits that file, the UI
  now surfaces the registration error instead of silently stalling.
- This phase improves the first-run path but does not yet add a browser-driven
  end-to-end test that clicks the new shortcut buttons.

## Follow-Up Tasks

- Add a browser smoke that clicks `Start with demo video` and verifies the UI
  lands on Model Connections with a registered source video.
- Consider exposing a server-reported demo video path instead of hard-coding the
  bundled example in the browser.
- Extend the same guided shortcut pattern to `Review previous result` and
  import-mask workflows.
