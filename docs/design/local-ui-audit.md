# Local UI Audit

Phase 03A captured the pre-redesign Local UI with the existing docs asset
script, then replaced the shell with a commercial product layout and a repeatable
Chrome layout gate.

## Baseline Evidence

Baseline screenshots are real local UI captures from:

```bash
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/baseline
```

The viewport baseline matrix was captured from a detached temporary worktree at
the pre-redesign `HEAD` so the current working tree did not need to be reverted:

```bash
git worktree add --detach /tmp/motionjson-phase03a-baseline-worktree HEAD
PYTHONPATH=/tmp/motionjson-phase03a-baseline-worktree/src \
  node /tmp/motionjson-phase03a-baseline-worktree/scripts/check_local_ui_layout.mjs \
  --screenshot-dir docs/design/screenshots/baseline-matrix
```

Key baseline captures:

![Baseline first-run UI](screenshots/baseline/local-ui-first-run.png)

![Baseline job review UI](screenshots/baseline/local-ui-job-review.png)

![Baseline 1366 real shell](screenshots/baseline-matrix/laptop-1366-real-empty-shell.png)

## Baseline Findings

- The first viewport exposed too many surfaces at once: project setup, viewer,
  wizard, config, first-run, capabilities, jobs, logs, artifacts, library,
  tracks, corrections, diagnostics, and routes.
- The 1440px desktop capture showed the wizard competing with the right rail,
  with narrow columns and clipped hierarchy.
- Advanced extraction parameters were open by default, so less-technical users
  had to read debug controls before they could follow the basic workflow.
- The right rail was a long stack of unrelated panels. Jobs, review, artifacts,
  corrections, asset library, and route diagnostics needed progressive
  disclosure.
- The shell relied on document-level scroll, which made project context,
  inspector context, and job state hard to keep in view.
- Accessibility basics existed: skip link, labels, keyboard shortcuts, and focus
  styles. The larger gap was layout predictability and information hierarchy.

## Redesign Evidence

The redesigned shell was validated with:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-03a
```

The check starts the mock/no-model UI, validates the real empty shell, seeds a
deterministic job-review state, validates the real seeded and fully expanded
shell, then captures docs states in headless Chrome. It verifies no horizontal
overflow or unintended side/panel overlap at:

- 1366x768 laptop
- 1440x900 desktop
- 1920x1080 desktop
- 1024x768 tablet-like width

Representative after captures:

![Redesigned 1440 first-run UI](screenshots/phase-03a/desktop-1440-first-run.png)

![Redesigned 1366 extraction wizard](screenshots/phase-03a/laptop-1366-extraction-wizard.png)

![Redesigned 1024 first-run UI](screenshots/phase-03a/tablet-1024-first-run.png)

## Fixes Made

- Added a stable app frame with left goal navigation, main workspace, and a
  right inspector.
- Added a visible guided workflow strip: create/open, add video, choose
  mode/model, confirm locality, run, review candidates, correct tracks, preview,
  export.
- Moved provider warnings into the extraction settings panel, close to the
  action they affect.
- Collapsed diagnostics-heavy surfaces into native disclosure sections:
  run monitor, review, artifacts and exports, corrections, asset library, and
  routes.
- Closed advanced extraction parameters by default.
- Added independent scroll containers on desktop and responsive collapse at
  narrower widths.
- Added a Node/Chrome layout regression script that fails on horizontal overflow
  and unintended panel overlap.

## Known Compromises

- The UI remains a dependency-free static HTML/CSS/JavaScript app. This phase did
  not migrate to React or add a component runtime.
- The viewer, prompt tools, and backend API wiring remain the existing
  implementation. Phase 03A changed the product shell and validation surface, not
  extraction semantics.
- The mock job used by screenshot/layout validation can emit Python resource
  tracker semaphore warnings during shutdown. The layout command exits
  successfully when the UI passes.
