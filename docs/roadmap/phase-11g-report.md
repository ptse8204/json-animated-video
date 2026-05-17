# Phase 11G Report: Local Asset Library UI

## Summary

Phase 11G surfaces the existing asset-library backend in the local UI. The
backend already supported reusable library assets, brand collections, and
creator-approved packs through SQLite, CLI, REST, SDK, and tests; this phase adds
local UI `/api/library/*` wrappers for the reserved local UI user and a compact
Asset Library panel in the right rail.

Users can now save an explicit generated/export artifact as a `motion_sticker`,
search saved layers, create brand collections, add the selected saved layer to a
collection, and create creator-approved packs when rights metadata permits. Pack
creation still uses the backend rights gate, so unapproved creator or
commercial-use metadata returns a visible error instead of creating a pack.
The UI persists selected library artifacts and collections across panel renders,
and only exposes explicit reusable layer/export artifact kinds for saving.

No new ML dependency, network call, hosted provider, commerce system, or public
marketplace listing is introduced. Library operations use existing local
database rows and report `aiUsage: "none"`.

## Changed Files

- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/favicon.svg`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `tests/test_local_ui_api.py`
- `docs/local_ui.md`
- `docs/asset_library_marketplace.md`
- `docs/roadmap/phase-11g-report.md`

## Tests Run

- `python3 -m compileall -q src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_asset_library_routes_save_collections_and_creator_packs tests/test_local_ui_api.py::test_local_ui_asset_library_pack_rejects_unapproved_layers -q` (`2 passed`)
- `python3 -m pytest tests/test_backend_asset_library.py tests/test_local_ui_api.py -q` (`33 passed`)
- `python3 -m pytest` (`291 passed`)
- `npm test` (`19 passed`)
- `npm run lint`
- `npm run build`
- `python3 -m motionjson.cli backend --help`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q` (`8 passed`)
- `git diff --check`
- Browser smoke: `python3 -m motionjson.cli ui --no-open --mock --db /tmp/motionjson-phase11g-smoke.sqlite --storage-root /tmp/motionjson-phase11g-smoke-storage --host 127.0.0.1 --port 8878`, then Playwright opened `http://127.0.0.1:8878/` and verified the Asset Library panel, `Save layer`, `Create pack`, and local library routes rendered without console errors.
- Bounded read-only review and follow-up verification: no remaining Phase 11G blockers after fixes for visible pack errors, selection persistence, saveable artifact filtering, and route inventory consistency.

## Known Limitations

- The local UI saves explicit artifacts selected from the current run; Phase 11G
  does not add track-level automatic asset materialization.
- The panel lists local saved layers and packs, but does not preview or download
  arbitrary saved library bytes. Artifact preview/opening still goes through the
  existing artifact browser.
- Creator packs remain metadata packs, not a public marketplace or paid creator
  commerce workflow.

## Follow-Up Tasks

- Add richer pack browsing and per-pack asset inspection if product scope needs
  it.
- Consider a track-specific “save selected object layer” command once every
  accepted track has a stable production artifact mapping.
- Continue the roadmap with final audit and launch polish after Phase 11G
  validation and review.
