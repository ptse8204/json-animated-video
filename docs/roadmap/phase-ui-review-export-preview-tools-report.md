---
historical: true
default_context: false
---

# Phase ui-review-export-preview-tools Report

## Summary

Repaired the Review/Export flow around completed run state, restored package preview tools as first-class review tools, and fixed the website package preview entrypoint path.

The completed-job inconsistency was caused by fresh `/api/jobs/{jobId}` data updating `state.selectedJob` while `state.jobs` still held an older running snapshot. The job list and active count render from `state.jobs`, so a completed selected run could still display `running` and `1 active`. The UI now merges fresh selected-job snapshots back into `state.jobs`, re-renders the job center after review refreshes, and uses normalized lifecycle state for active-job decisions.

## Changed Files

- `src/motionjson/ui/static/app.js`
  - Added stale job list reconciliation after selected job review refreshes.
  - Normalized active-job lifecycle checks so terminal jobs cannot remain active through stale raw status.
  - Added Review tools metadata, cards, iframe selection, and full-view links.
  - Added safe preview-file URL support.
- `src/motionjson/ui/static/index.html`
  - Added the Review tools panel and export-rail compact tool list.
- `src/motionjson/ui/static/app.css`
  - Added responsive styling for review tool cards and the embedded tool frame.
- `src/motionjson/ui/server.py`
  - Added `GET/HEAD /api/jobs/{jobId}/preview-files/{relPath}`.
  - Whitelisted package preview files, runtime JS, safe JSON manifests, spritesheets, and cutouts.
  - Blocked traversal, local absolute paths, logs, run configs, provider diagnostics, masks, and other non-preview artifacts.
  - Sanitized JSON preview responses through public review redaction.
- `src/motionjson/exporters/website_package.py`
  - Fixed `preview/index.html` to load `../scene_graph.json`.
  - Added package manifest `previewTools` metadata for canvas player, object selection workflow, and timeline editor.
- Tests updated in `scripts/test_ui_config_builder.mjs`, `tests/test_local_ui_api.py`, and `tests/test_final_export.py`.

## Model Package Evaluation

Evaluated `/Users/edwintse/Downloads/content-test-result`.

- The package contains a valid compact result with `scene_graph.json`, `web_asset_manifest.json`, runtime JS, spritesheet assets, and the three dedicated preview tools.
- `preview/canvas_player.html`, `preview/object_selection_workflow.html`, and `preview/timeline_editor.html` load when served from the package with correct relative paths.
- The broken file was `preview/index.html`: it requested `./scene_graph.json`, which resolves to `preview/scene_graph.json`. The actual scene graph is at package root, so preview index must request `../scene_graph.json`.

## Tests Run

- `npm test`
- `npm run embed:smoke`
- `python3 -m pytest -q tests/test_final_export.py::test_website_package_zip_is_relative_self_contained_and_excludes_debug_assets tests/test_local_ui_api.py::test_local_ui_preview_file_route_serves_review_tools_and_blocks_unsafe_paths tests/test_local_ui_api.py::test_local_ui_preview_file_route_serves_imported_result_directories tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_job_lifecycle.py tests/test_phase9_ui_job_review_smoke.py`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-ui-review-export-preview-tools`
- `git diff --check`

`npm run ui:layout` passed across the required viewport/state matrix and produced screenshot evidence under `docs/design/screenshots/phase-ui-review-export-preview-tools/`. It emitted a Python multiprocessing resource tracker warning during shutdown, but the command returned status `ok`.

## Chrome Evidence

The original Colab target disconnected, so live verification used a local debug-mock UI at `http://127.0.0.1:54433/`.

Verified in Chrome:

- Completed mock run displayed `succeeded`.
- Job center displayed `0 active`.
- Job list chip displayed `succeeded`, not stale `running`.
- Review & export step displayed one object row.
- Review tools showed all three tools as `Ready`.
- Inline iframe rendered:
  - Canvas player loaded `object_0` from `../web_asset_manifest.json`.
  - Object selection workflow loaded scene and asset manifests.
  - Timeline editor loaded layer/timeline controls.
- Validate export returned `Valid`.
- Export generated handoff cards for Website package, MotionJSON scene, Runtime snippet, Remotion plan, and Developer bundle.

Saved Chrome evidence:

- `docs/design/screenshots/phase-ui-review-export-preview-tools/chrome-local-review-tools.png`

## Known Limitations

- Existing packages already exported with the old `preview/index.html` path still contain the old broken reference. New packages are fixed.
- The Local UI exposes only whitelisted preview package files through the preview-file route. Raw logs, provider diagnostics, masks, run configs, and arbitrary local paths remain intentionally unavailable.
- The iframe uses local package HTML/JS and is intended for trusted local MotionJSON result packages, not arbitrary web content.

## Follow-Ups

- Add a package repair/import action that can rewrite old `preview/index.html` files when importing historical packages.
- Consider showing package manifest `previewTools` metadata in the UI when it is available, while keeping the built-in tool list as a fallback.
