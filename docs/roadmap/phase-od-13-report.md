---
historical: true
default_context: false
---

# Phase OD-13 Report — Selected Object Export Workflows

## Summary

Phase OD-13 improves selected-object handoff from the API/backend export path.
Validated local UI exports now write an API-owned `object_layer_pack.json`, a
selected-object `website_package.zip`, and export validation messages alongside
the corrected `scene_graph.json`, final manifest, validation report, quality
routing, previews, and ZIP bundle.

Headless asset-package jobs now accept optional `objectIds` and package only
those scene objects. Unknown selected object ids fail clearly instead of
producing an empty package. Remotion adapter plans now include selected object
ids, discovery/review metadata, and an object-layer pack contract without
installing dependencies or invoking npm/network.

## Changed Files

- `src/motionjson/exporters/object_layer_pack.py`
- `src/motionjson/exporters/website_package.py`
- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/backend/jobs.py`
- `src/motionjson/backend/api.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/exporters/final_render.py`
- `src/motionjson/exporters/remotion.py`
- `src/motionjson/schemas/motionjson.final_export_manifest.v0.1.schema.json`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `packages/motionjson-sdk/src/index.js`
- `packages/motionjson-sdk/test/sdk.test.mjs`
- `scripts/build_ui_shell.mjs`
- `tests/test_final_export.py`
- `tests/test_local_ui_api.py`
- `tests/test_backend_jobs_worker.py`
- `README.md`
- `docs/final_export.md`
- `docs/runtime.md`
- `docs/developer_api.md`
- `docs/local_ui.md`
- `docs/schemas.md`
- `docs/index.md`

## Tests Run

- `python3 -m py_compile src/motionjson/exporters/object_layer_pack.py src/motionjson/exporters/website_package.py src/motionjson/backend/export_workflows.py src/motionjson/exporters/final_render.py src/motionjson/backend/jobs.py src/motionjson/backend/api.py src/motionjson/backend/worker.py src/motionjson/exporters/remotion.py src/motionjson/ui/server.py`
- `python3 -m pytest tests/test_final_export.py tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_local_ui_api.py::test_local_ui_export_validation_messages_explain_unreviewed_auto_discovery tests/test_backend_jobs_worker.py::test_export_worker_packages_existing_extraction_with_no_ai_usage -q`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state job-review --viewport laptop-1366,tablet-1024`
- `python3 scripts/capture_docs_assets.py --check`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m motionjson.cli backend diagnostics --json`
- `git diff --check`

## Known Limitations

- The Remotion path remains a JSON adapter plan only. It does not install
  Remotion, run npm, or generate an application component.
- `object_layer_pack.json` is a handoff manifest and snippet/template contract;
  it does not introduce a new runtime schema loader.
- The targeted `job-review` layout smoke passed but emitted Python's existing
  `resource_tracker` leaked semaphore shutdown warning.
- Rendering scout was attempted before commit, but the Codex app returned
  `agent thread limit reached`. Local layout, embed, and export tests covered
  the changed UI/export surfaces instead.

## Follow-up Tasks

- Add richer object-layer pack templates if downstream adopters need framework
  specific packaging beyond the current snippets.
- Consider exposing selected-object package options in the CLI after the API/UI
  flow stabilizes.
