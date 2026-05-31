# Phase ui-upload-project-review-flow Report

## Summary

This phase repaired the Local UI flow around starting work and finishing review export:

- Added a direct browser upload path that creates a local project automatically when needed, registers the source video as a local asset, and prepares the browser preview from that registered asset.
- Changed the Video step from local-path-first to upload-first. The CLI-style local path field now lives in an advanced disclosure and no longer defaults to `examples/demo_red_ball.mp4`.
- Made the project rail `+ New` action move the user directly to the upload step instead of focusing a hidden or indirect project form.
- Connected `object_selection_workflow.html` to the Local UI review/export API so the tool can export the actual selected completed run, not only demonstrate a simulated prompt flow.
- Fixed a parent UI status mismatch after iframe export: the main export panel and studio review rail now both fall back to the stored `export_validation_report` artifact, so a finished export cannot show `Valid` in one place and `Not validated` in another.
- Kept the previously repaired review-tool surface intact: canvas player, object selection workflow, and timeline editor are discoverable in Review & export and open through the safe preview-file route.

## Findings

- The original upload path forced users to create or select a project, then type a filesystem path. That made the happy path brittle and caused the workflow CTA to be disabled before users could simply pick a file.
- The object selection workflow had the right review concepts but was still framed as a standalone demo. It now reads `review` and `export` URLs from the Local UI tool URL, enables `Export MotionJSON`, and posts an export-complete message back to the parent UI.
- Chrome file chooser automation could not complete because the Codex Chrome Extension does not currently have file URL access enabled in this profile. The exact user-facing remediation was reported during verification. The multipart upload API path is covered by tests, and Chrome verified the upload-first UI state.
- `/Users/edwintse/Downloads/content-test-result` is an older generated package. Its `preview/index.html` still loads `./scene_graph.json` from inside `preview/`, while the scene file is at the package root. Its `package_manifest.json` also has no `previewTools` metadata. The exporter fix for new packages is already present in the preceding committed phase `ecbf817`; this existing directory should be regenerated to pick it up.

## Changed Files

- `src/motionjson/ui/server.py`
  - Added `POST /api/videos/upload` with multipart parsing, safe filename handling, automatic local project creation, asset registration, preview preparation, and public video payload return.
- `src/motionjson/ui/static/index.html`
  - Added the upload-first Video step card and moved local path registration into an advanced disclosure.
- `src/motionjson/ui/static/app.js`
  - Added FormData-aware API requests, upload status state, direct upload flow, upload-first workflow actions, review-tool API query params, iframe export completion handling, and shared export-validation fallback logic.
- `src/motionjson/ui/static/app.css`
  - Added responsive upload card styling.
- `examples/object_selection_workflow.html`
- `examples/object_selection_workflow.js`
  - Added the Local UI-connected `Export MotionJSON` action and parent postMessage handoff.
- `scripts/build_ui_shell.mjs`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
  - Added route checks, upload-first workflow expectations, and export-validation fallback tests.
- `tests/test_local_ui_api.py`
- `tests/test_object_selection_workflow.py`
- `tests/test_final_export.py`
  - Added direct upload API tests and review-tool/export package assertions.
- `docs/local_ui.md`
- `docs/run_local.md`
  - Documented direct upload as the normal Local UI path.
- `docs/design/screenshots/phase-ui-upload-project-review-flow/`
  - Saved the full layout matrix and Chrome verification screenshot.

## Tests Run

- `npm test`
  - Passed: 21 tests.
- `npm run embed:smoke`
  - Passed: embed status `Loaded object_0`, visible canvas pixels verified.
- `python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_direct_video_upload_creates_project_and_video tests/test_local_ui_api.py::test_local_ui_direct_video_upload_requires_real_multipart_file tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_object_selection_workflow.py tests/test_final_export.py::test_website_package_zip_is_relative_self_contained_and_excludes_debug_assets`
  - Passed: 9 tests.
- `npm run build`
  - Passed: dependency-free static UI shell check.
- `npm run ui:layout -- --state workflow-export --viewport desktop-1440 --screenshot-dir docs/design/screenshots/phase-ui-upload-project-review-flow-debug`
  - Passed after fixing the export-status fallback.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-ui-upload-project-review-flow`
  - Passed across 6 viewports and 60 capture states. Python emitted a multiprocessing `resource_tracker` leaked semaphore warning at shutdown, but the layout tool returned `status: ok`.

## Chrome Evidence

Live target used instead of the disconnected Colab runtime:

- `http://127.0.0.1:55775/`

Chrome verified:

- `+ New` moves to the Video step.
- Direct upload card is visible.
- Primary CTA is `Choose video file`.
- Local path disclosure is closed.
- `#videoPath` is empty.
- Completed run review shows `0 active` and job chip `succeeded`.
- Object selection workflow loads through `/api/jobs/{jobId}/preview-files/preview/object_selection_workflow.html` with `scene=../scene_graph.json`, `manifest=../web_asset_manifest.json`, `review=...`, and `export=...`.
- Clicking iframe `Export MotionJSON` returns `Export complete. Open scene_graph.json Open package`.
- Parent UI updates both `#exportStatus` and `#studioExportStatus` to `Valid`.
- Handoff cards show ready outputs for website package, MotionJSON scene, runtime snippet, and developer handoff.

Screenshot:

- `docs/design/screenshots/phase-ui-upload-project-review-flow/chrome-upload-review-export.png`

## Known Limitations

- Chrome file chooser automation was blocked by extension permission: the Codex Chrome Extension needs file URL access before automated `setFiles(...)` can exercise the real picker path. Backend multipart upload tests cover the actual route.
- The existing `/Users/edwintse/Downloads/content-test-result` package was not modified in place. Regenerate it with the current exporter to fix `preview/index.html` and manifest metadata.
- The layout smoke command still reports a Python multiprocessing semaphore cleanup warning at process shutdown. The UI layout checks themselves passed.

## Follow-Ups

- Add a small UI affordance that explains why automated browser upload checks may require Chrome extension file URL access.
- Consider showing package manifest `previewTools` metadata in the Review tools list when available, while keeping the built-in tool list as a fallback.
