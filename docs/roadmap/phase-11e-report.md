# Phase 11E Report: Export Quality Routing

## Summary

Phase 11E adds deterministic export quality routing for validated local UI
exports. Each export now writes `quality_routing.json` and embeds the same
routing data in `final_export_manifest.json` under `qualityRouting`.

Routing is derived from cached object quality scores, `recommendedOutput`,
export preset options, cached production assets, and the resource profile. It
does not rerun SAM2, detectors, matting, hosted providers, LLMs, VLMs, or
network services.

The local UI export panel now shows the quality-routing summary, selected
object output route, delivery route, MP4 preview status, and links to the new
export artifacts. Public artifact content remains allowlisted, path-redacted,
and local-only.

Review fixes in this phase add Windows/UNC path redaction before raw export JSON
is written, keep validation MP4 preview as a dry run, remove partial MP4 files
on encode failure, choose the smallest ready production delivery asset when no
optimizer-selected route exists, and invalidate stale routing display when
export controls change.

## Changed Files

- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/exporters/final_render.py`
- `src/motionjson/schemas/motionjson.final_export_manifest.v0.1.schema.json`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_final_export.py`
- `tests/test_local_ui_api.py`
- `docs/final_export.md`
- `docs/local_ui.md`
- `docs/quality_engine.md`
- `docs/schemas.md`
- `docs/roadmap/phase-11e-report.md`

## Tests Run

- `python3 -m compileall -q src/motionjson/backend/export_workflows.py src/motionjson/exporters/final_render.py src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `git diff --check`
- `python3 -m pytest tests/test_final_export.py tests/test_local_ui_api.py -q` (`33 passed`)
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_final_export.py::test_mp4_final_render_reports_cached_no_ai_manifest -q` (`2 passed`)
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli export --help`
- `python3 -m pytest` (`286 passed`)
- `npm test` (`19 passed`)
- `npm run lint`
- `npm run build`
- Browser smoke at `http://127.0.0.1:8876/` with a mock export: the export
  API reported validation MP4 preview as `plan_ready` and final export MP4
  preview as `ready`; the export panel showed the stale-routing warning after
  controls changed, then showed `quality routing`, `MP4 preview ready`, and
  links for `quality_routing.json` after the matching preset was selected.
  Browser console errors were empty.

Environment note: `python` is not on this PATH, so validation used `python3`.

## Known Limitations

- MP4 preview generation depends on local FFmpeg. Missing FFmpeg or encoder
  failures are reported as `unavailable` or `error` in routing instead of
  blocking JSON export.
- Preflight validation reports MP4 preview as `plan_ready` when FFmpeg is
  available; encoding happens only during final export.
- Routing selects among already cached production assets. It does not create new
  sprite atlases, AVIF atlases, or transparent WebM assets during validated UI
  export.
- CLI export behavior is preserved. The new quality-routing artifact is scoped
  to local UI validated exports.
- In-app browser screenshot capture timed out during smoke validation; DOM and
  console checks completed successfully.

## Follow-Up Tasks

- Continue Phase 11F with user-visible rights and lineage warnings on export.
- Consider adding a standalone schema file for
  `motionjson.export_quality_routing.v0.1` if downstream consumers need to
  validate the auxiliary `quality_routing.json` directly.
- Add multi-object UI screenshots for export routing once screenshot capture is
  stable in the local browser harness.
