---
historical: true
default_context: false
---

# Phase Runtime 08 Report: SAM3 Text Workflow Routing Guard

Generated: 2026-06-05T22:56:38-07:00

## Summary

Fixed the guided `Find by description` path so it no longer defaults to the local SAM3 Scene Sweep connection and then fails with the official-package `sam3`/`SAM3_LOCAL_MODEL` error. The UI now treats text/concept discovery as a hosted SAM3 concept workflow by default, keeps the legacy detector path explicit, and blocks local SAM3 concept/exemplar validation when the advanced official SAM3 adapter is unavailable.

The key contract is now explicit: SAM3 Scene Sweep can propose visible objects, but it is not a local text prompt adapter. Local `sam3_concept` requires the official SAM3 package plus a local `sam3.pt` checkpoint path; hosted SAM3 concept providers remain the normal guided path for text prompts.

## Changed Files

- `src/motionjson/ui/static/app.js`
  - Changed the normal `text_detector` model priority to hosted SAM3 concept providers.
  - Kept `sam3-local` only as an advanced text option.
  - Made explicit `textDiscoveryProvider=detector` route to the detector path.
  - Corrected capability-warning lookups for `sam3_concept` and `sam3_exemplar`.
- `src/motionjson/ui/static/config_builder.js`
  - Matched the guided config helper to the hosted-by-default text workflow.
  - Populates SAM3 concept config from the resolved provider, not only from the raw selector value.
  - Corrected provider warning lookup names.
- `src/motionjson/ui/server.py`
  - Added discovery-mode to capability-name mapping.
  - Added a targeted validation blocker for local SAM3 concept/exemplar runs when the official adapter is unavailable.
- `src/motionjson/provider_settings.py`
  - Removed local SAM3 from the normal `text_detector` supported goals.
  - Clarified setup copy: Scene Sweep uses `sam3-transformers`; text prompts need hosted concept or advanced official SAM3.
- `docs/local_ui.md`
  - Documented the corrected `Find by description` routing.
- Tests updated:
  - `tests/test_local_ui_api.py`
  - `tests/test_phase8_ui_config_builder.py`
  - `tests/test_provider_settings.py`
  - `scripts/test_ui_config_builder.mjs`

## Tests Run

- `node scripts/test_ui_config_builder.mjs` - passed.
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_validation_uses_sam3_auto_masks_for_scene_sweep_warnings tests/test_local_ui_api.py::test_local_ui_validation_blocks_unconfigured_local_sam3_concept tests/test_phase8_ui_config_builder.py` - passed.
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py::test_first_run_summary_does_not_make_advanced_sam3_package_a_scene_sweep_blocker tests/test_capabilities.py::test_sam3_local_capability_explains_unset_model_path tests/test_local_ui_api.py::test_local_ui_validation_uses_sam3_auto_masks_for_scene_sweep_warnings tests/test_local_ui_api.py::test_local_ui_validation_blocks_unconfigured_local_sam3_concept tests/test_phase8_ui_config_builder.py` - passed.
- `npm test` - passed.
- `npm run build` - passed.
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_phase8_ui_config_builder.py` - passed.
- `python3 -m motionjson.cli --help` - passed.
- `python3 -m motionjson.cli extract --help` - passed.
- `git diff --check` - passed.

## Known Limitations

- This phase does not implement a new local text detector or make SAM3 Scene Sweep understand text prompts. It prevents the incorrect local concept run from starting and routes normal text search to hosted concept setup.
- Advanced local SAM3 concept/exemplar remains possible only when the official `sam3` package and a local `sam3.pt` checkpoint are installed/configured.
- No browser screenshots were captured because this phase changes routing, validation, and setup copy, not layout or visual structure.

## Follow-Up Tasks

- Add a clearer in-flow action from the blocked validation message to either hosted SAM3 setup or Trace all objects / Scene Sweep.
- Consider adding a lightweight candidate-labeling workflow after Scene Sweep so users can search/filter discovered objects by label without requiring text-guided segmentation.
