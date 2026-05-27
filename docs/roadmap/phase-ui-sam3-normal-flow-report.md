# Phase Report - SAM3 Normal Flow Diagnostics and UI Alignment

## Summary

- Retried Colab MCP three times. The connector failed from this session: first
  the transport closed, then a later retry timed out after 120 seconds. No Colab
  browser was controllable, so validation continued through the local UI,
  notebook-facing docs, diagnostics, and screenshot tooling.
- Repaired the normal SAM3 Scene Sweep diagnostics so `Find everything in
  scene` no longer presents the advanced official-package `sam3-local` blocker
  (`Python module 'sam3' is not importable`, `SAM3_LOCAL_MODEL`, `sam3.pt`) as
  the user-facing failure. The normal blocker is now `sam3-auto-masks
  [sam3-transformers]` with the Model setup action.
- Kept `sam3-local` as the advanced official-package concept/exemplar adapter
  and made its provider setup copy say that the local `sam3.pt` path is not
  required for normal scene sweep.
- Fixed the old Advanced `Discover objects` preset so it has compatible model
  choices instead of showing "No compatible model connection".
- Moved the main shell closer to the storyboard: the left rail now behaves as a
  project list, old accordion panels are hidden in normal mode, Model setup no
  longer duplicates the selected provider card, and the video step uses a
  preview/settings split on desktop.

## Changed Files

- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/index.html`
- `tests/test_capabilities.py`
- `tests/test_ui_first_run_simplicity.py`
- `docs/provider_capabilities.md`
- `docs/design/screenshots/ui-sam3-normal-flow/`

## Validation

- `python3 -m py_compile src/motionjson/capabilities.py src/motionjson/provider_settings.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m pytest -q tests/test_capabilities.py tests/test_provider_settings.py tests/test_ui_first_run_simplicity.py`
- `python3 -m motionjson.cli backend diagnostics --text | rg -n "sam3-local|sam3-auto-masks|SAM3 local adapter|Scene Sweep|sam2-hf"`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-sam3-normal-flow/after --state workflow-goal,workflow-video,workflow-provider,model-setup-sam3-local,prepare-sam3-trace-all,workflow-run,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`

The layout command passed. It emitted the known non-fatal Python
`resource_tracker` semaphore cleanup warning at shutdown.

## Screenshot Evidence

- Before baseline copied from the prior committed UI phase:
  `docs/design/screenshots/ui-sam3-normal-flow/before/`
- After captures:
  `docs/design/screenshots/ui-sam3-normal-flow/after/`

Required viewports were captured: `390x844`, `768x1024`, `1024x768`,
`1366x768`, `1440x900`, and `1920x1080`.

## Known Limitations

- Colab MCP was not available in this session, so this phase could not click
  through a live Colab browser.
- The UI is closer to the storyboard but not pixel-identical. Remaining visual
  work should replace the older static shell structure with first-class
  storyboard components instead of adding more override CSS.
- Real SAM3 Scene Sweep still requires the user to install/cache the
  Transformers runtime and have access to `facebook/sam3`.

## Follow-Up Tasks

- Add a notebook smoke path that can be run headlessly without Colab MCP.
- Continue converting the older static panels into explicit storyboard
  components so fewer CSS overrides are needed.
- Add an end-to-end fake first-run UI test for `Find everything in scene` from
  setup through run recovery and export.
