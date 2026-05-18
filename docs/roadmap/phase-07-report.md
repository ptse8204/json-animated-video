# Phase 07 Report: Review, Correction, And Export Recovery

Date: 2026-05-17

## Summary

Phase 07 strengthened the object review and correction loop without adding
new ML dependencies or pretending that partial reruns are available. Track
edits now write a durable `review_state_manifest` artifact that captures
correction history, included/excluded track IDs, compact track review state,
raster fallback status, and `aiUsage: "none"`. The local UI exposes that
artifact through the safe local artifact route.

The UI review surface now has a selected Track Detail panel showing source,
coverage, geometry, preview visibility, export inclusion, warnings, repair
state, and related artifacts. Review overlays can render polygon/contour
geometry from track frames and fall back to boxes when polygons are missing.

Docs now include a realistic bad-mask recovery walkthrough: inspect a bad
track, exclude or delete it before export, save a no-model repair request when
the UI cannot materialize repair assets, use the deterministic CLI correction
path for materialized mask edits, then import the repaired result for review
and validated export.

The working tree was not clean at phase start because `.motionjson/`,
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, `docs/Codex Prompt Instrcution.md`,
and `out/demo_red_ball/` were untracked local/generated artifacts. They were
not staged for this phase.

## Changed Files

- `src/motionjson/backend/corrections.py`
  - Adds `motionjson.local_ui_review_state_manifest.v0.1`.
  - Writes or updates `review/review_state_manifest.json` after track edits.
  - Keeps repair/add-object as explicit no-model hooks when no partial rerun
    worker is available.
- `src/motionjson/ui/server.py`
  - Exposes `review_state_manifest` as a safe downloadable local artifact.
  - Includes manifest metadata in job review payloads.
- `src/motionjson/ui/static/index.html`, `app.css`, `app.js`
  - Adds the Track Detail review panel.
  - Highlights selected tracks and renders related artifacts.
  - Draws polygon/contour overlays when track frame geometry provides them.
  - Surfaces `review_state_manifest` in fallback/review diagnostics.
- `docs/local_ui.md`, `docs/mask_correction.md`,
  `docs/assets/README_ASSETS.md`
  - Document review-state manifests, correction/export audit state, and the
    bad-mask-to-repaired-track workflow with the existing job review screenshot.
- Tests:
  - `tests/test_backend_track_corrections.py`
  - `tests/test_backend_api_product.py`
  - `tests/test_phase9_ui_job_review_smoke.py`
  - `scripts/build_ui_shell.mjs`

## Tests Run

- `python3 -m py_compile src/motionjson/backend/corrections.py src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `git diff --check`
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_backend_track_corrections.py tests/test_backend_api_product.py::test_rest_api_track_edits_persist_corrections_and_update_artifacts tests/test_phase9_ui_job_review_smoke.py -q`
  - Result: 7 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_phase10_track_edit_workflows.py tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_local_ui_api.py::test_local_ui_export_excludes_pending_add_object_until_assets_are_materialized tests/test_local_ui_api.py::test_local_ui_artifact_review_surfaces_fallback_without_private_storage tests/test_mask_corrections.py::test_correct_cli_regenerates_manifests_quality_and_validates tests/test_track_filtering.py -q`
  - Result: 16 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_docs_assets.py tests/test_docs_links.py tests/test_phase13_packaging_onboarding.py::test_extraction_mode_docs_include_failure_modes_and_multi_object_sample -q`
  - Result: 9 passed.
- `python3 -m pytest -q`
  - Result: 247 passed.
- `npm test -- --runInBand`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.

## Screenshots And Demos Produced

No new screenshots were produced. The walkthrough references the existing
generated `docs/assets/local-ui-job-review.png`, and
`docs/assets/README_ASSETS.md` documents how to regenerate it.

## Review

Reviewer subagent found a blocking public-artifact risk in the first
`review_state_manifest` implementation: raw correction payload strings could
have been served through the artifact content route. The manifest is now
sanitized before storage, and a regression test verifies local paths,
Windows-style paths, storage-key-like strings, and `storageKey` fields do not
leak through `/api/artifacts/ARTIFACT_ID/content`. The reviewer also flagged
stale screenshot wording and incomplete frontend command results; both were
fixed in docs and this report.

## Known Limitations

- UI `repair_track` and `add_object` remain saved no-model hooks unless a
  future worker materializes masks, cutouts, and object manifests.
- Split/merge update review state and export inclusion, but full downstream
  per-object asset regeneration for every non-UI export path remains future
  work.
- The new Track Detail panel is still in the right-rail review flow; a larger
  dedicated review workspace can build on the same manifest and overlay data.
- No new screenshot was captured for an actual bad-mask repair sequence.

## Follow-Up Tasks

- Materialize deterministic UI repair requests through the existing CLI mask
  correction engine when the selected job has mask artifacts.
- Teach legacy render/package workers to consume the same corrected review
  state used by validated UI exports.
- Add an automated browser smoke that walks fallback diagnosis, repair request,
  review-state manifest creation, validation, and export.
- Capture a dedicated bad-mask recovery screenshot once the UI repair flow can
  seed that state deterministically.

## 2026-05-18 Revalidation

Phase 07 was rechecked after the commercial UI redesign. The correction docs
still include the bad-mask-to-repaired-track walkthrough, reference the real
job-review screenshot, and explain `review/review_state_manifest.json` as the
durable review/export audit artifact. A docs regression assertion now protects
that walkthrough and screenshot reference.
