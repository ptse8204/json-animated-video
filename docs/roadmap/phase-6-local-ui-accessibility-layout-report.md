---
historical: true
default_context: false
---

# Phase 6 Report: Accessibility and Layout Regression Coverage

## Summary

Phase 6 hardened the guided Local UI shell for keyboard and assistive-technology use. Collapsed sidebar and diagnostics regions now become `inert` in addition to using `aria-hidden`, the workflow stepper advertises keyboard shortcuts, and Arrow key/Home/End navigation moves the active workflow step while keeping the target step focusable. The layout smoke script now validates these states across the commercial viewport matrix.

No backend API, config generation, extraction, correction, or export behavior changed.

## Changed files

- `src/motionjson/ui/static/index.html`
  - Added `aria-keyshortcuts` to the workflow stepper.
- `src/motionjson/ui/static/app.js`
  - Added Arrow/Up/Down/Home/End keyboard support for workflow steps.
  - Made collapsed sidebar content and collapsed diagnostics rail inert.
  - Kept focus on shell controls or active steps after collapse/keyboard actions.
- `scripts/check_local_ui_layout.mjs`
  - Added the `workflow-keyboard` state.
  - Added assertions for `aria-controls`, inert collapsed regions, open diagnostics rail accessibility, workflow keyboard movement, and focusability.
  - Kept post-run failure diagnostics coverage from Phase 4.
- `scripts/build_ui_shell.mjs`
  - Added a static affordance check for inert collapsed regions.
- `docs/design/screenshots/phase-6-accessibility-layout/`
  - Captured accessibility/layout screenshots for the new regression states.

## Browser evidence

Screenshots were captured under `docs/design/screenshots/phase-6-accessibility-layout/`.

Before visual evidence for this phase is the committed Phase 4 after-screenshot set under `docs/design/screenshots/phase-4-review-export-flow/after/`. Phase 6 intentionally changed accessibility state handling and regression coverage rather than visual layout. The Phase 6 screenshots confirm the same guided shell still renders cleanly after adding inert hidden regions and keyboard handling.

Screenshot matrix covered:

- States: `real-empty-shell`, `nav-collapsed`, `diagnostics-open`, `workflow-keyboard`, `workflow-dashboard`, `workflow-review-failure`, `workflow-export`
- Viewports: `mobile-390`, `tablet-768`, `tablet-1024`, `laptop-1366`, `desktop-1440`, `desktop-1920`

Representative checks:

- Collapsed navigation keeps only compact brand/goal/menu visible.
- Diagnostics rail can open accessibly and is no longer inert while open.
- Keyboard navigation exercises ArrowRight, ArrowLeft, Home, End, and ArrowDown, then leaves Project active and focusable.
- Failed review state keeps backend/fallback diagnostics visible; the mobile full-page capture includes fallback diagnostic rows.
- Show-all dashboard mode remains available.

## Tests run

- `node --check src/motionjson/ui/static/app.js`
- `node --check scripts/check_local_ui_layout.mjs`
- `npm run build`
- `npm test`
- `npm run lint`
- `npm run embed:smoke`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli ui --help`
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state real-empty-shell,nav-collapsed,diagnostics-open,workflow-keyboard,workflow-dashboard,workflow-review-failure,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-6-accessibility-layout`

Validation result: all commands passed. The layout run printed the existing Python `resource_tracker` leaked semaphore warning at mock UI shutdown.

## Known limitations

- The layout script validates keyboard movement and focusability through Chrome DevTools Protocol, not a full screen-reader pass.
- The full all-state `npm run ui:layout` remains expensive; this phase used the targeted accessibility/layout state matrix plus `--check`.
- Separate before screenshots were not recaptured at Phase 6 start; the Phase 4 after set is used as the pre-Phase-6 visual baseline because Phase 6 did not intentionally change visual layout.

## Follow-up tasks

- Add more keyboard-specific states if future steps introduce modal dialogs or drawers.
- Keep new hidden regions covered by inert/aria assertions in `scripts/check_local_ui_layout.mjs`.
