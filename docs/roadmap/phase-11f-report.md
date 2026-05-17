# Phase 11F Report: Rights And Lineage Export Warnings

## Summary

Phase 11F makes existing rights metadata and asset lineage visible in the local
review/export workflow. Validated local UI exports now return `rightsSummary`
and `exportWarnings`, embed `exportWarnings` in `final_export_manifest.json`,
and record `validated_motionjson_export` lineage plus rights rows for generated
handoff artifacts.

The UI now surfaces rights status in selected-track detail and export warnings
in the export panel. The warnings are conservative and non-blocking: they call
out unverified commercial-use status, missing creator approval, unverified or
unknown licenses, and attribution requirements. No network, hosted AI, legal
clearance, or new ML dependency is introduced.

A read-only review found a legacy compatibility blocker where schema-valid
`sourceAttribution: true` or `false` values could crash the new review/export
rights summary path. Phase 11F now normalizes that legacy shape centrally and
adds regression coverage for both legacy rights metadata and fully approved
rights metadata with no warnings.

## Changed Files

- `src/motionjson/rights.py`
- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/exporters/final_render.py`
- `src/motionjson/schemas/motionjson.final_export_manifest.v0.1.schema.json`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_final_export.py`
- `tests/test_local_ui_api.py`
- `tests/test_rights_metadata.py`
- `docs/final_export.md`
- `docs/local_ui.md`
- `docs/rights_and_lineage.md`
- `docs/schemas.md`
- `docs/roadmap/phase-11f-report.md`

## Tests Run

- `python3 -m compileall -q src/motionjson/rights.py src/motionjson/backend/export_workflows.py src/motionjson/exporters/final_render.py src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `git diff --check`
- `python3 -m pytest tests/test_final_export.py tests/test_local_ui_api.py tests/test_rights_metadata.py tests/test_backend_rights_lineage.py -q` (`40 passed`)
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q` (`8 passed`)
- `python3 -m pytest` (`289 passed`)
- `npm test` (`19 passed`)
- `npm run lint`
- `npm run build`
- `python3 -m motionjson.cli backend --help`
- Browser smoke at `http://127.0.0.1:8877/` with a mock run and validated
  export: the API returned rights warnings
  `commercial_use_review_required`, `creator_approval_unverified`,
  `license_unverified`, and `attribution_required`; the UI showed Rights,
  License, Attribution, `rights and lineage`, and the warning codes in the
  export panel with no browser console errors.

Environment note: `python` is not on this PATH, so validation used `python3`.

## Known Limitations

- Rights warnings are metadata review prompts, not legal clearance or legal
  advice.
- The local UI can display current rights metadata, but Phase 11F does not add
  an editing form for rights fields. Existing CLI/backend metadata inputs remain
  the source of truth.
- Export warnings are intentionally non-blocking so local-first handoff remains
  possible for internal review.

## Follow-Up Tasks

- Continue Phase 11G with reusable asset library and pack workflows if the
  existing backend support is sufficient.
- Add UI editing for rights metadata in a later workflow if product scope calls
  for it.
- Consider a dedicated `motionjson.export_rights_summary.v0.1` schema if
  downstream consumers need strict validation of the auxiliary rights summary.
