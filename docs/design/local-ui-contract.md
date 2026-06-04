# Local UI Contract

This document records the small state contracts used by the dependency-free
Local UI. Keep it implementation-oriented so future engineers and Codex agents
can change the interface without rereading the full `app.js`.

## Project Drawer

- The guided workspace is full width by default.
- Project switching, recent projects, workspace preferences, Local API status,
  and capabilities live in the contextual project drawer.
- `projectShellStateFromSnapshot()` is the pure source for project drawer
  labels and accessibility state.
- Rendering may set DOM attributes and focus, but selector inputs must be plain
  objects such as `{ sidebarCollapsed, selectedProject }`.
- A closed drawer must expose `aria-hidden="true"` and inert drawer content.
  An open drawer must set the project button to `aria-expanded="true"`.

## Adaptive Parameters

- `adaptiveRunDefaultsFromSnapshot()` computes guided defaults from goal,
  provider, video metadata, prior failure reason, and user overrides.
- Guided mode should show readable chips before raw fields: sample FPS, max
  frames, max objects, scene sweep quality, device, and materialization risk.
- Advanced controls remain editable. Every field should show `Auto tuned` or
  `User override`, and user overrides can be reset to auto.
- Asset-prep and heartbeat failures on scene sweep should bias retries toward
  lower sample FPS, fewer frames, fewer objects, and clean scene sweep quality.

## Help Text

- `OPTION_HELP_TEXT` is the canonical copy map for critical options.
- Critical labels use the existing `data-tooltip` primitive and must be
  keyboard-focusable when the help is not otherwise obvious.
- Required help topics are scene sweep quality, sample FPS, max frames, max
  objects, trace-everything mode, device, export preset, and partial-result
  recovery.

## Review And Export

- `review_export` is one workflow step with two sub-screens: `review` and
  `export`.
- `reviewExportScreenStateFromSnapshot()` is the pure source for headings,
  guide title, status label, summaries, and default primary labels.
- Review focuses on object decisions: object list, quality warnings,
  keep/reject/export inclusion, previews, and corrections.
- Export focuses on package readiness: validation, package type, included
  objects, rights notes, generated artifacts, and handoff actions.
- There should be one visible primary workflow CTA per state.

## Partial Result Recovery

- Failed jobs can still be reviewable when completed objects, candidates, or
  reviewable object counts are present.
- Partial failures should route to Review, show completed objects, and surface
  the failed object/frame/reason when backend metadata is available.
- Export remains gated by review and validation; partial success does not mean
  silent export.

## Layout States

The layout checker should continue covering these UX-critical states:

- `real-empty-shell`
- `workflow-goal`
- `workflow-video`
- `prepare-sam3-trace-all-runtime-ready`
- `project-drawer-open`
- `workflow-run-asset-stalled`
- `workflow-review`
- `workflow-export`
- `workflow-partial-success`
- `job-review`

Passing layout checks must mean the state is usable, not merely non-overlapping:
content is nonblank, drawers and rails have correct accessibility state, mobile
actions do not cover content, Review and Export are distinct, and duplicate
primary export CTAs are not visible.
