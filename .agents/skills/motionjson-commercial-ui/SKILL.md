---
name: motionjson-commercial-ui
description: Use for MotionJSON Local UI product redesign, app-shell layout, information architecture, responsive panels, accessibility basics, and commercial-grade visual hierarchy.
---

# MotionJSON Commercial UI

Use this skill before changing `src/motionjson/ui/static/*`, docs screenshots, or UI shell behavior.

## Product Standard

- Design for a local-first video object-layer editing product used by creators, web developers, editors, and ML/CV experimenters.
- Default to a guided, nontechnical path: create/open project, add video, choose extraction mode/provider, confirm local/hosted settings, run, review, correct, preview, export.
- Keep advanced diagnostics available, but behind tabs, details panels, or separate views.
- Avoid dashboard clutter: one primary task per screen, clear hierarchy, and visible recovery paths.

## Layout Rules

- Use a stable app frame: top bar, left navigation/project rail, main workspace, contextual right inspector, and bottom job/timeline area only when useful.
- Define layout, spacing, typography, z-index, border, focus, and status tokens before adding ad hoc CSS.
- Prevent horizontal page overflow at laptop/desktop widths: 1366x768, 1440x900, 1920x1080, and 1024-wide tablet-like layouts.
- Menus, dialogs, dropdowns, toasts, tooltips, inspectors, and timeline/status panels must not overlap incorrectly or hide primary controls.
- Use fixed/sticky regions sparingly and with named z-index tokens.

## Components And States

- Inventory and reuse primitives for buttons, inputs, tabs, segmented controls, cards/panels, dialogs, dropdowns, toasts, provider cards, status chips, progress, object rows, and preview shells.
- Each major screen needs empty, loading, error, offline/no-provider, disabled, and success states.
- Use plain product language. Avoid making users understand SAM2/provider internals before starting the safe mock path.

## Accessibility

- Every control needs an accessible name.
- Visible focus states must be present and high contrast.
- Dialogs and popovers need Escape-to-close behavior where implemented.
- Keyboard tab order should follow the visible layout.
- Do not rely only on color for status.

## Validation

- Capture screenshots before and after major UI changes.
- Add repeatable viewport checks for layout overflow and critical-region overlap.
- Record validation commands and known compromises in the phase report.
