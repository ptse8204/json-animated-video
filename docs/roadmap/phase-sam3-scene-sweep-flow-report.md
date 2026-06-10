---
historical: true
default_context: false
---

# SAM3 Scene Sweep Flow Repair Report

## Summary

Implemented the SAM3 scene-sweep repair as a coherent local UI and backend slice. The public `sam3_auto_masks` discovery mode now runs a scene sweep instead of routing to `sam3_concept` with the broad prompt `object`: it samples keyframes, calls a SAM3 Tracker-compatible automatic mask generator, filters/dedupes masks into reviewable candidates, and tracks accepted candidates through SAM3 Tracker Video when available.

The guided UI now treats "find everything in the scene" as a separate scene-sweep workflow, keeps concept search separate, makes model options respond to the selected model/profile, advances the lower-page content on every Continue step, and exposes failed-run recovery actions (`Open logs`, `Change setup`, `Run again`, `Choose model`).

Initial worktree state was clean (`git status --short` returned no tracked modifications) before implementation.

Research references used:

- https://huggingface.co/docs/transformers/en/model_doc/sam3_tracker
- https://huggingface.co/facebook/sam3
- https://huggingface.co/docs/transformers/en/model_doc/sam3_video
- https://github.com/facebookresearch/sam3

## Changed Files

- Backend/provider runtime: `src/motionjson/providers/sam3.py`, `src/motionjson/providers/discovery.py`
- Capability and provider diagnostics: `src/motionjson/capabilities.py`, `src/motionjson/provider_settings.py`, `pyproject.toml`
- Local UI flow/config: `src/motionjson/ui/static/app.js`, `src/motionjson/ui/static/config_builder.js`, `src/motionjson/ui/static/index.html`, `src/motionjson/ui/static/app.css`
- UI validation scripts: `scripts/check_local_ui_layout.mjs`, `scripts/test_ui_config_builder.mjs`
- Tests: `tests/test_sam3_providers.py`, `tests/test_discovery_providers.py`, `tests/test_phase8_ui_config_builder.py`, `tests/test_provider_settings.py`
- Docs: `docs/sam3_local.md`, `docs/sam3_hosted.md`, `docs/run_config.md`, `docs/provider_capabilities.md`, `docs/discovery_providers.md`
- Browser evidence: `docs/design/screenshots/sam3-scene-sweep-flow/before/`, `docs/design/screenshots/sam3-scene-sweep-flow/after/`

## Validation

- `python3 -m pytest tests/test_sam3_providers.py -q` - passed before broader regression checks.
- `python3 -m pytest tests/test_sam3_providers.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_phase8_ui_config_builder.py tests/test_docs_links.py -q` - 80 passed, 1 skipped.
- `python3 -m pytest tests/test_sam3_providers.py tests/test_discovery_providers.py -q` - 65 passed, 1 skipped.
- `python3 -m pytest -q` - 470 passed, 1 skipped.
- `npm test` - 21 passed.
- `npm run lint` - passed.
- `npm run build` - passed.
- `python3 -m motionjson.cli --help` - passed.
- `python3 -m motionjson.cli extract --help` - passed.
- `python3 -m motionjson.cli backend --help` - passed.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/sam3-scene-sweep-flow/after --state workflow-goal,workflow-video,workflow-provider,workflow-prompts,workflow-run,prepare-sam3-trace-all,workflow-review-failure,model-setup-sam3-local --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920` - passed with a non-fatal Python resource tracker semaphore cleanup warning at shutdown.

## Browser Evidence

Before screenshots were captured under `docs/design/screenshots/sam3-scene-sweep-flow/before/` before implementation. After screenshots were captured under `docs/design/screenshots/sam3-scene-sweep-flow/after/` after implementation.

Viewports captured for both before and after: 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and 1920x1080.

States captured for both before and after: `workflow-goal`, `workflow-video`, `workflow-provider`, `workflow-prompts`, `workflow-run`, `prepare-sam3-trace-all`, `workflow-review-failure`, and `model-setup-sam3-local`.

Key observed changes:

- `workflow-provider` now renders the model step's lower content instead of carrying the broader setup content forward.
- `prepare-sam3-trace-all` now presents the no-prompt trace-all run step and recovery actions for terminal jobs without blocking new runs.
- `workflow-review-failure` now exposes failed-run recovery in the main panel and details rail: open logs, run again, change setup, and choose model.
- SAM3 trace-all config no longer includes the concept/text prompt `object`; it carries `sceneSweep: true` and SAM3 Tracker settings.

## Known Limitations

- The real SAM3 Tracker runtime remains optional and is not imported in CI. Tests use fake mask-generation and tracker-video runtimes to cover control flow and payload shape.
- The Transformers SAM3 Tracker Video invocation may still need adjustment for exact version-specific output tensor shapes in real GPU environments.
- Hosted SAM3 scene sweep is only enabled for custom hosted profiles that explicitly advertise automatic mask generation. Roboflow SAM3 remains concept-only.
- The scene-sweep filtering defaults are conservative (`maxMaskAreaRatio`, dedupe, stability support) and may need tuning against real videos.

## Follow-Up Tasks

- Run a real SAM3 Tracker scene-sweep smoke test on a machine with the `sam3-transformers` extra and accessible `facebook/sam3` weights.
- Add a small recorded fixture once a real SAM3 Tracker output shape is confirmed, so output normalization remains pinned.
- Consider workflow-specific readiness messaging for the umbrella "SAM3 local" setup card so concept/exemplar and scene-sweep readiness are visually separated even more clearly.
