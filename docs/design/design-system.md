# MotionJSON Local UI Design System

Historical implementation evidence: this file describes the current static UI
shell and layout checks. It is not a redesign requirement. Use
`docs/product/ui_redesign_brief.md` for current form-agnostic UI redesign work.

Phase 03A establishes a small static design system for the local product shell.
The implementation lives in `src/motionjson/ui/static/app.css`.

## Tokens

- Spacing: `--space-2xs`, `--space-xs`, `--space-sm`, `--space-md`,
  `--space-lg`, `--space-xl`.
- Radius: `--radius-xs`, `--radius-sm`, `--radius-md`, `--radius-lg`.
- Z-index: `--z-sidebar`, `--z-sticky`, `--z-popover`, `--z-toast`.
- Status colors:
  - ready/action: `--ready`, `--ready-soft`;
  - diagnostic/API: `--api`, `--api-soft`;
  - warning: `--warn`, `--warn-soft`;
  - error: `--bad`, `--bad-soft`;
  - review/accent: `--violet`, `--violet-soft`.

## Shell

- `.app-shell` is the desktop grid: side navigation, workspace, inspector.
- `.sidebar`, `.workspace`, and `.right-rail` scroll independently on desktop.
- `.workspace-grid` uses named grid areas for `viewer`, `setup`, `wizard`, and
  `config`.
- At `max-width: 1180px`, the inspector moves below the workspace.
- At `max-width: 560px`, forms, workflow steps, timeline controls, wizard fields,
  and action groups become single-column.

## Components

- Goal buttons: `.goal`, `.goal.is-active`.
- Panels: `.panel`, `.compact-panel`.
- Inspector groups: `.rail-section`, implemented with native `details`.
- Status chips: `.status-chip` plus `is-ready`, `is-warn`, `is-bad`,
  `is-neutral`, `is-muted`, and `is-violet`.
- Viewer: `.viewer-panel`, `.viewer-toolbar`, `.viewer-stage`,
  `.timeline-controls`.
- Form/action controls: `.inline-form`, `.wizard-fields`, `.config-actions`,
  `.load-config-button`.
- Review rows: `.artifact-row`, `.candidate-row`, `.track-row`,
  `.diagnostic-row`, `.history-row`, `.suggestion-row`.

## Accessibility

- A skip link jumps to `#workspaceMain`.
- Native buttons, inputs, selects, and `details` summaries keep keyboard
  behavior.
- Focus-visible outlines use `--focus`.
- Tooltip content appears on hover and keyboard focus.
- The layout check verifies that at least one visible control exposes a focus
  style in each captured state.

## Validation

Use:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-03a
```

The script fails on:

- horizontal overflow;
- side navigation, workspace, and inspector overlap;
- workspace panel overlap;
- missing core shell elements;
- absent visible focus style.

It checks the real empty shell, the real seeded shell, the fully expanded shell,
and the docs capture states used by README screenshots.
