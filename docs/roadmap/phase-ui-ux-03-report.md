# Phase UI-UX-03 Report: Adaptive Run Parameters

## Summary

- Added a pure adaptive-parameter helper exported under `MotionJSONUI`.
- Guided prepare screens now show readable `Auto tuned` chips for sample FPS,
  max frames, max objects, scene sweep quality, device, and materialization
  risk.
- Expert edits to tuned fields are preserved as user overrides until the user
  chooses `Reset to auto`.
- Critical options now have keyboard-focusable tooltip labels, including scene
  sweep quality, sample FPS, max frames, max objects, trace-everything mode,
  device, export preset, and partial-result recovery.
- Layout gates now fail when prepare screens lose auto-tuned chips or visible
  help/source affordances.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_ui_first_run_simplicity.py`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-ux-03-before/`
- `docs/design/screenshots/ui-ux-03/`

## Tests Run

- `npm run ui:layout -- --state prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all-runtime-ready,advanced-config --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-03-before`
- `node scripts/test_ui_config_builder.mjs`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py`
- `npm run ui:layout -- --state prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all-runtime-ready,advanced-config --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/ui-ux-03`
- `npm run ui:layout -- --state prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all-runtime-ready,advanced-config --screenshot-dir docs/design/screenshots/ui-ux-03`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`
- `python3 -m pytest -q tests/test_ui_first_run_simplicity.py tests/test_phase03a_local_ui_layout.py`

## Known Limitations

- The before capture for this phase used representative mobile and desktop
  prepare states. The after capture ran the full 390, 768, 1024, 1366, 1440,
  and 1920 viewport matrix.
- The adaptive helper is still in `app.js` for this phase to avoid static import
  risk. Phase UI-UX-05 should extract mature pure helpers into small modules.
- The Python mock UI shutdown can still emit a resource tracker warning after
  layout captures.

## Follow-Up Tasks

- Phase UI-UX-04: split Review and Export into visually distinct workspaces and
  route partial-success runs to reviewable output.
- Phase UI-UX-05: extract adaptive parameters, help copy, and product-state
  selectors into dedicated dependency-free modules.
