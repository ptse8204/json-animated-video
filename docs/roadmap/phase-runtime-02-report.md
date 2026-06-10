---
historical: true
default_context: false
---

# Phase runtime-02: Partial review payload synthesis

## Summary

This phase makes completed object checkpoints reviewable when a later object fails before global export artifacts are written. The backend now synthesizes the missing root review package from completed `objects/*/object_manifest.json` files:

- `scene_graph.json`
- `web_asset_manifest.json`
- per-object `objects/{objectId}/web_asset_manifest.json`
- `tracks.json`
- `fallback_diagnostics.json`
- `rights_manifest.json`
- `partial_review.json`
- preview tool files under `preview/`

The worker writes these artifacts before marking the job failed, then registers them with the normal output-tree path. The existing review/readiness code can therefore surface partial tracks and preview tools without a parallel UI contract.

Partial review synthesis is best-effort and cannot mask the original extraction failure. If synthesis itself fails, the worker records a `partial_review_payload_failed` event and still marks/registers the original failed job normally.

The helper also refuses to overwrite an already-complete root review package. If `scene_graph.json`, `web_asset_manifest.json`, and `tracks.json` already exist, synthesis returns `root_review_payload_exists` and leaves those files unchanged.

No layout surfaces were changed in this phase, so browser screenshot evidence was not required.

## Changed files

- `src/motionjson/backend/partial_review.py`
  - Added `synthesize_partial_review_payload(...)`.
  - Reconstructs a partial scene from completed object manifests.
  - Copies preview tools and writes root/object web manifests.
  - Marks synthesized tracks as review-required and partial.
- `src/motionjson/backend/worker.py`
  - Calls partial review synthesis on provider/config and generic extraction failures.
  - Emits `partial_review_payload_ready` and `partial_preview_tools_ready` when synthesis succeeds.
  - Registers `partial_review.json` as a backend asset kind.
- `src/motionjson/job_artifacts.py`
  - Registers `partial_review.json` in generated artifact scanning.
- `src/motionjson/ui/server.py`
  - Reads `partial_review` artifacts into review metadata.
- `tests/test_backend_jobs_worker.py`
  - Adds no-model worker failure coverage that proves a completed object remains reviewable after a later failure.
  - Asserts synthesized artifacts satisfy the existing review readiness gate.
  - Covers the guard that prevents partial synthesis from overwriting an already-complete root review payload.
- `tests/test_local_ui_api.py`
  - Adds API-level review coverage for `partialSuccess`, `partialReview`, `reviewableObjectCount`, and diagnostic redaction.
- `docs/local_ui.md`
  - Documents partial object recovery behavior for `/api/jobs/JOB_ID/review`.
- `docs/schemas.md`
  - Documents `motionjson.partial_review_payload.v0.1` as an auxiliary recovery payload.
- `docs/roadmap/phase-runtime-02-report.md`
  - Records this phase.

## Tests run

- `python3 -m py_compile src/motionjson/backend/partial_review.py src/motionjson/backend/worker.py src/motionjson/job_artifacts.py src/motionjson/ui/server.py`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py::test_extract_worker_synthesizes_partial_review_payload_after_object_failure tests/test_backend_jobs_worker.py::test_partial_review_synthesis_does_not_overwrite_complete_root_payload tests/test_local_ui_api.py::test_local_ui_review_exposes_partial_review_payload_and_redacts_diagnostics`
- `python3 -m pytest -q tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_job_artifacts.py tests/test_local_ui_api.py`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_job_lifecycle.py tests/test_job_artifacts.py tests/test_final_export.py`
- `npm test`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known limitations

- Partial review synthesis uses completed object manifests. It cannot recover an object whose manifest was not checkpointed before failure.
- Synthesized partial tracks default to review-required/export-included false. Users must inspect and include them before export.
- The helper copies preview tools from the repository examples/runtime assets. It does not produce a rendered MP4 preview.
- Explicit stale-job reconciliation from already-registered storage rows is still handled by the older recovery path. This phase covers live worker failures where the temporary output tree still exists.

## Follow-up tasks

- Extend explicit stale recovery to synthesize root review artifacts from registered storage assets when the temporary output tree is gone.
- Add a visible partial-review diagnostic row in the review workbench for failed object/frame details.
- Move expensive spritesheet/cutout generation behind accepted candidates to reduce failure surface for complex runs.
- Add CUDA/MPS/CPU runtime proof endpoint for the current notebook process.
