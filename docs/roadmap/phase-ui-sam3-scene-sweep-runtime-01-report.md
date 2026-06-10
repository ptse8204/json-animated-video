---
historical: true
default_context: false
---

# UI-SAM3-SCENE-SWEEP-RUNTIME-01 Report

## Summary

- Fixed Prepare & run capability warnings so `sam3_auto_masks` validates the
  `sam3-auto-masks` Scene Sweep capability instead of the advanced official
  `sam3-local` concept/exemplar adapter.
- Kept `sam3-local`/`SAM3_LOCAL_MODEL` warnings for advanced SAM3
  concept/exemplar workflows, while preventing that checkpoint-path blocker
  from appearing as the normal `Find everything in scene` failure.
- Aligned SAM3 Scene Sweep diagnose after local cache selection: cached local
  Hugging Face model directories now validate through the effective custom
  model value rather than the internal `__custom__` sentinel.
- Added deterministic layout capture states for Scene Sweep runtime ready,
  missing runtime, missing cache, failed cache, and cached success paths.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/server.py`
- `src/motionjson/provider_settings.py`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `tests/test_local_ui_api.py`
- `tests/test_provider_settings.py`
- `docs/design/screenshots/ui-sam3-scene-sweep-runtime-01-before/`
- `docs/design/screenshots/ui-sam3-scene-sweep-runtime-01/`

## Tests Run

- `node --check src/motionjson/ui/static/app.js`
- `npm test`
- `npm run build`
- `python3 -m py_compile src/motionjson/provider_settings.py src/motionjson/ui/server.py`
- `python3 -m pytest tests/test_provider_settings.py tests/test_local_ui_api.py -q`
- `python3 -m pytest tests/test_provider_settings.py tests/test_local_ui_api.py tests/test_capabilities.py tests/test_sam3_providers.py -q`
- `npm run ui:layout -- --state prepare-sam3-trace-all,prepare-sam3-trace-all-runtime-ready,prepare-sam3-trace-all-missing-runtime,model-setup-sam3-local,model-setup-sam3-missing-runtime,model-setup-sam3-missing-cache,model-setup-cache-failed,model-setup-cache-success --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-sam3-scene-sweep-runtime-01`
- `git diff --check`

The layout command passed and emitted the existing non-fatal Python
`resource_tracker` leaked semaphore warning at shutdown.

## Browser Evidence

- Before screenshots: `docs/design/screenshots/ui-sam3-scene-sweep-runtime-01-before/`
  with 28 files for the existing Scene Sweep Prepare and Model setup cache
  states.
- After screenshots: `docs/design/screenshots/ui-sam3-scene-sweep-runtime-01/`
  with 56 files covering the existing states plus deterministic
  runtime-ready, missing-runtime, and missing-cache states.
- Viewports checked: `390x844`, `768x1024`, `1024x768`, `1366x768`,
  `1440x900`, and `1920x1080`.

## Known Limitations

- Before screenshots do not include the new deterministic runtime-ready and
  missing-runtime states because those capture states were added in this phase.
- The optional concept/exemplar diagnose checklist still includes
  `SAM3_LOCAL_MODEL` as an advanced, non-required row. The normal Scene Sweep
  Prepare warning path no longer uses that row as the blocker.

## Review

- Ran one read-only diff-review scout before commit.
- Scout reported no blocking concerns and recommended proceeding to commit.

## Follow-Up Tasks

- Consider splitting the advanced official SAM3 concept/exemplar setup card
  into a separate UI affordance if future user testing shows the optional
  checklist rows are still distracting.
