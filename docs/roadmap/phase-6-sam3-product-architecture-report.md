# Phase 6 Report: SAM3 Product Architecture

## Summary

Phase 6 separates SAM3 into explicit user-facing product paths while preserving executable run-config compatibility. The registry now exposes distinct workflow entries for no-model CPU fallback, SAM2 prompt tracking, SAM2 HF scene fallback, SAM3 Scene Sweep, hosted SAM3 concept/text discovery, and advanced local SAM3 concept/exemplar. Run configs still use the worker-supported provider names such as `sam3-local`, `sam3-hosted`, `sam2-local`, `sam2-hf-auto-masks`, and `mock`.

Validation now emits stable SAM3 product-path error codes for scene-sweep runtime failures, hosted opt-in/credential blockers, and advanced local checkpoint blockers. The Local UI model setup flow shows SAM3 Scene Sweep separately from SAM2 HF fallback, no-model CPU workflow, hosted SAM3 text discovery, and advanced local SAM3 concept/exemplar.

Required read-only scouts were used:

- `plan-risk-scout`: identified the need to keep product path ids separate from executable worker provider names, split advanced local SAM3 from Scene Sweep, add stable SAM3 validation codes, and preserve no-model/SAM2 aliases.
- `diff-review-scout`: found no blocking code issues, but required this current phase report and more relevant SAM3 browser evidence before commit. Both findings were addressed before commit.

## Changed Files

- `src/motionjson/provider_registry.py`: added first-class product workflow entries, aliases, worker provider mappings, validation policies, and fallbacks.
- `src/motionjson/provider_settings.py`: clarified `sam3-local` as normal SAM3 Scene Sweep setup and kept checkpoint-based concept/exemplar as advanced-only.
- `src/motionjson/capabilities.py`: recommends `sam3_tracker_scene_sweep` for CUDA scene sweep and `no_model_cpu_workflow` for CPU/MPS first-run fallback.
- `src/motionjson/ui/server.py`: maps new SAM3 validation warnings to stable error codes and blocks hosted/advanced local paths with product-specific diagnostics.
- `src/motionjson/ui/static/modules/provider_connections.js`: split model setup cards into SAM3 Scene Sweep, SAM2 HF fallback, no-model CPU workflow, hosted SAM3 text discovery, and advanced local SAM3.
- `src/motionjson/ui/static/config_builder.js` and `src/motionjson/ui/static/app.js`: normalize product path ids back to executable provider names and preserve mock/no-model run-config generation.
- `scripts/check_local_ui_layout.mjs`, `scripts/test_local_ui_e2e.mjs`, and `scripts/test_ui_config_builder.mjs`: added product-path UI coverage and updated assertions for the new labels.
- `tests/test_provider_registry.py`, `tests/test_local_ui_api.py`, `tests/test_provider_settings.py`, and `tests/fixtures/local_ui_workflow_matrix.v0.1.json`: cover product path mapping, validation codes, hosted credential blockers, and scene-sweep/advanced-local separation.
- `README.md` and `docs/sam3_local.md`: document the product paths and the distinction between Scene Sweep Transformers setup and advanced checkpoint setup.
- `docs/design/screenshots/phase-6-sam3-product-architecture/`: before/after browser evidence for model setup states.

## Validation

- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm test` -> 23 passed.
- `npm run test:e2e` -> 8 passed after the final model setup fixture changes.
- `python3 -m pytest` -> 616 passed, 1 skipped.
- `python3 -m pytest tests/test_provider_registry.py tests/test_local_ui_api.py::test_capability_environment_profile_recommends_sam3_for_cuda_gpu tests/test_local_ui_api.py::test_capability_environment_profile_guides_cpu_and_mps_fallbacks tests/test_local_ui_api.py::test_local_ui_validation_uses_sam3_auto_masks_for_scene_sweep_warnings tests/test_local_ui_api.py::test_local_ui_validation_blocks_unconfigured_local_sam3_concept tests/test_local_ui_api.py::test_local_ui_blocks_hosted_sam3_without_per_run_ack_after_provider_opt_in tests/test_local_ui_api.py::test_local_ui_validation_reports_sam3_hosted_missing_credentials tests/test_local_ui_workflow_matrix.py::test_local_ui_run_config_validation_matrix -q` -> 31 passed.
- `python3 -m pytest tests/test_local_ui_api.py tests/test_local_ui_workflow_matrix.py tests/test_provider_registry.py tests/test_sam3_providers.py -q` -> 118 passed, 1 skipped.
- `python3 -m pytest tests/test_provider_settings.py::test_sam3_scene_sweep_setup_guide_is_not_advanced_checkpoint_setup tests/test_provider_settings.py::test_sam_goal_capabilities_are_declared_for_guided_ui -q` -> 2 passed.
- `python3 -m py_compile src/motionjson/ui/server.py src/motionjson/provider_registry.py src/motionjson/provider_settings.py src/motionjson/capabilities.py` -> passed.
- CLI smoke passed:
  - `python3 -m motionjson.cli --help`
  - `python3 -m motionjson.cli extract --help`
  - `python3 -m motionjson.cli backend --help`
- `git diff --check` -> passed.

## Browser Evidence

Baseline screenshots:

- `npm run ui:layout -- --state model-setup --screenshot-dir docs/design/screenshots/phase-6-sam3-product-architecture/before` captured the default Model setup screen before Phase 6.
- From detached Phase 5 commit `1dfddd5`, `npm run ui:layout -- --state model-setup-sam3-local --screenshot-dir /Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/phase-6-sam3-product-architecture/before` passed for 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and 1920x1080.
- Additional Phase 5 before screenshots for hosted/fallback model setup states are present for visual comparison. The broad Phase 5 capture wrote the images but failed stale label assertions in the old harness, so the validated before baseline is the SAM3 Scene Sweep state above.

After screenshots:

- `npm run ui:layout -- --state model-setup --screenshot-dir docs/design/screenshots/phase-6-sam3-product-architecture/after` passed for the six required viewports.
- `npm run ui:layout -- --state model-setup-trace-all-options,model-setup-sam3-local,model-setup-sam2-hf-fallback,model-setup-no-model-cpu,model-setup-sam3-roboflow,model-setup-sam3-custom,model-setup-advanced-local-sam3 --screenshot-dir docs/design/screenshots/phase-6-sam3-product-architecture/after` passed for the six required viewports.
- `npm run ui:layout -- --state model-setup-advanced-local-sam3 --screenshot-dir docs/design/screenshots/phase-6-sam3-product-architecture/after` passed after the final advanced-local label fix.

Representative after evidence shows trace-all alternatives listing SAM3 Scene Sweep, SAM2 HF automatic masks fallback, No-model CPU workflow, and Hosted SAM3 text discovery as separate cards. Advanced local SAM3 concept/exemplar is visible only in the advanced-compatible trace-one/text setup path and no longer inherits the Scene Sweep card label.

## Known Limitations

- Product path ids are registry/UI concepts; executable backend jobs still use existing worker provider names for compatibility.
- Advanced local SAM3 concept/exemplar remains blocked unless the official SAM3 package and a local `sam3.pt` checkpoint path are configured and runtime proof exists.
- Hosted SAM3 profile capabilities are still adapter/profile dependent. The UI requires explicit hosted opt-in and credentials before network-capable runs.
- No-model CPU workflow is intentionally a fallback/smoke path. It does not claim semantic object discovery.

## Follow-Up Tasks

- Add provider-profile-specific runtime probes once real hosted SAM3 adapters are available.
- Consider exposing product workflow ids in diagnostics export payloads without changing the executable run-config schema.
- Continue to refine advanced local SAM3 setup copy after official package installation paths stabilize.
