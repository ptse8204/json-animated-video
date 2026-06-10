---
historical: true
default_context: false
---

# Phase UI-MODEL-05c Report

## Summary

This phase reworked the guided Local UI navigation around a 5-step flow:
Goal, Video, Model, Prepare, and Review. The wizard now uses a sticky footer
with one explicit primary CTA per step, consistent `Back` navigation, and
auto-advance after successful step actions. Guided mode no longer requires an
explicit early project decision; adding a video, using the demo video, or
opening an existing result creates a starter local project automatically.

The visual hierarchy was tightened so important actions are filled and stable,
while setup tests, diagnostics, resets, and advanced controls are clearly
secondary. The browser capture harness and JS workflow tests were updated to
assert the new 5-step contract, CTA labels, and simplified guided states.

Before screenshots:
- [docs/design/screenshots/ui-model-05c/before](/Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/ui-model-05c/before)

After screenshots:
- [docs/design/screenshots/ui-model-05c/after](/Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/ui-model-05c/after)

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/build_ui_shell.mjs`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `docs/local_ui.md`

## Tests Run

- `npm test`
- `npm run build`
- `npm run lint`
- `python3 -m pytest tests/test_phase8_ui_config_builder.py tests/test_local_ui_api.py -q`
- `python3 -m pytest -q`
- `npm run ui:layout -- --state first-run,workflow-goal,workflow-video --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-model-05c/after`
- `npm run ui:layout -- --state prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all,workflow-review --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-model-05c/after`
- `npm run ui:layout -- --state model-setup-sam3-local,model-setup-sam3-custom,prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all,workflow-review --viewport tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-model-05c/after`

## Known Limitations

- The layout harness completes successfully, but the Python worker emits a
  `multiprocessing.resource_tracker` leaked-semaphore warning on some capture
  runs during shutdown. The screenshots and assertions still completed.
- The advanced dashboard still exposes the legacy panel model internally. This
  phase simplified the guided path and CTA contract without deleting the older
  advanced surfaces.

## Follow-up Tasks

- Collapse or restyle the inline `Add video` button so the sticky footer is the
  only materially prominent forward action in the video step.
- Continue narrowing review-side secondary actions so correction and export
  controls feel more obviously grouped under the guided review step.
- Consider splitting the internal advanced-panel routing away from the guided
  step ids so future UI work no longer carries the legacy panel aliases.
