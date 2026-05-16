# Phase 11 Report - Export Validation and Interoperability

## Summary

Phase 11 adds a local-first validated MotionJSON export workflow for corrected
review state. The local UI can now validate and export a selected job through
presets (`compact`, `debug`, `vector-heavy`, `raster-fallback`), write
downloadable generated export artifacts, import a previous MotionJSON result
for review, and surface validation/provenance metadata without exposing storage
keys or local absolute paths.

Reviewer follow-up hardened import/export safety: import paths reject symlinks
before validation or registration, public API errors redact local paths, SVG
preview labels are XML-escaped, imported SVGs remain metadata-only instead of
same-origin public content, validation failures do not register export
artifacts, export validation honors the same toggles as export, and pending
add-object/split correction hooks are diagnosed and excluded from validated
exports until corresponding scene assets exist.

The existing CLI `export` and `validate` commands are preserved. The final
export manifest schema now accepts optional `provenance`, `config`, and
`validation` blocks, and manifests use `source.directory: "."` to avoid
machine-specific paths.

The phase started from a dirty working tree. The unrelated dirty files were
pre-existing `README.md`, `out/demo/**`, `AGENTS_old.md`, `README_old.md`, and
generated `out/demo` preview/runtime artifacts; they were left unstaged and
untouched.

## Changed Files

- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/backend/jobs.py`
- `src/motionjson/exporters/final_render.py`
- `src/motionjson/schemas/motionjson.final_export_manifest.v0.1.schema.json`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `tests/test_local_ui_api.py`
- `tests/test_final_export.py`
- `scripts/test_ui_config_builder.mjs`
- `docs/local_ui.md`
- `docs/final_export.md`
- `docs/schemas.md`
- `docs/developer_api.md`
- `docs/roadmap/phase-11-report.md`

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/backend/export_workflows.py src/motionjson/ui/server.py src/motionjson/exporters/final_render.py src/motionjson/backend/jobs.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result -q`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py -q` (`19 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py tests/test_final_export.py tests/test_schema_validation.py tests/test_phase10_track_edit_workflows.py tests/test_backend_track_corrections.py -q` (`40 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` (`212 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli export --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `python -m pytest tests -k export -q` failed because `python` is not
  available in this shell (`zsh:1: command not found: python`); the equivalent
  `python3` command below passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k export -q` (`22 passed, 190 deselected`)
- `node --check src/motionjson/ui/static/app.js`
- `node scripts/test_ui_config_builder.mjs`
- `npm test` (`19 passed`)
- `npm run lint`
- `npm run build`
- Local API path-leakage probe using `LocalUIApp`: mock export response omitted
  temp paths/storage keys and returned a schema-valid exported scene.

Browser smoke:

- Started `python3 -m motionjson.cli ui --db /tmp/motionjson-phase11-browser-8793.sqlite --storage-root /tmp/motionjson-phase11-browser-8793-storage --no-open --mock --host 127.0.0.1 --port 8793`.
- Seeded a project, registered `examples/demo_red_ball.mp4`, ran a mock job,
  saved a pending `add-object` correction hook, validated, and exported the
  `compact` preset.
- Opened the local UI in the in-app browser and verified the Export panel
  reported `Valid`, `1 included`, `1 excluded from export`, a `pending
  corrections` warning, and public links for generated export artifacts.
  Browser console errors: none.

## Known Limitations

- The validated local UI export creates a corrected MotionJSON scene handoff
  and supporting artifacts; it does not enqueue the older backend render/package
  workers for MP4/WebM/website ZIP formats.
- If every object track is excluded or deleted, export fails clearly with a
  no-exportable-track message instead of emitting an invalid empty scene graph.
- `add_object` and `repair` remain persisted no-model hooks until a later
  partial-rerun worker can materialize new masks/assets; validated export now
  excludes and diagnoses unmaterialized correction tracks.
- Preview export is currently an SVG frame overlay, not an encoded preview
  video. FFmpeg-dependent preview video export remains future work.

## Follow-Up Tasks

- Extend backend render/package workers to consume the same corrected export
  state when producing website ZIP, MP4, WebM, or Remotion outputs.
- Add a multi-object fixture that exercises export inclusion with one included
  and one excluded object in a fully materialized scene.
- Add optional FFmpeg preview-video export when FFmpeg is available, while
  preserving the current no-model SVG overlay path.
- Consider a CLI-facing validated MotionJSON handoff command once the UI/API
  workflow stabilizes.
