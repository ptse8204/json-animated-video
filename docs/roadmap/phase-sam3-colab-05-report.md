# Phase SAM3 Colab 05 Report: Model Connections SAM3 Path Helper

## Summary

Added low-risk Model Connections guidance for local SAM3 model paths. The SAM3
local provider field now carries a checkpoint-specific placeholder and helper
text:

`Use the local sam3.pt checkpoint file path. Do not enter /content/sam3 or facebook/sam3.`

The existing Model Setup and Provider Settings forms now render provider field
helper text under local config inputs. The helper is visible wherever the SAM3
local config field is rendered, while hosted SAM3 flows remain unchanged.

## Changed Files

- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `tests/test_provider_settings.py`
- `tests/test_phase03b_provider_settings_ui.py`
- `docs/design/screenshots/sam3-colab-05-before/`
- `docs/design/screenshots/sam3-colab-05/`
- `docs/roadmap/phase-sam3-colab-05-report.md`

## Browser Evidence

Before screenshots:

- `docs/design/screenshots/sam3-colab-05-before/`

After screenshots:

- `docs/design/screenshots/sam3-colab-05/`

Captured states and viewports:

- states: `provider-settings`, `model-setup`, `model-setup-local`
- viewports: `mobile-390`, `tablet-768`, `tablet-1024`, `laptop-1366`,
  `desktop-1440`, `desktop-1920`

The layout gate reported `status: ok` for the after matrix. The current capture
fixtures do not scroll directly to the SAM3 local field, so static/API tests
verify the helper text is present in provider metadata and rendered by the UI
component path.

## Tests Run

- `python3 -m pytest tests/test_provider_settings.py tests/test_phase03b_provider_settings_ui.py -q`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --state provider-settings,model-setup,model-setup-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/sam3-colab-05-before`
- `npm run ui:layout -- --state provider-settings,model-setup,model-setup-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/sam3-colab-05`
- `git diff --check`

## Known Limitations

- No new interactive pre-save warning was added; invalid values are caught by
  provider diagnose/backend diagnostics from Phase 3.
- The existing capture fixtures still default the local model setup screenshot
  to SAM2 local, so the SAM3 helper is verified by source/API tests rather than
  a direct visible screenshot.

## Follow-Up Tasks

- Consider adding a dedicated `model-setup-sam3-local` capture fixture if the
  screenshot suite later needs direct visual evidence for this helper text.
- Run the full available validation suite before final handoff.
