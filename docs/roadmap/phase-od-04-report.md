# Phase OD-04 Report - Selected Candidate Tracking API

## Summary

Phase OD-04 adds backend-owned selected-candidate tracking routes:

- `POST /api/jobs/{jobId}/track-selected`
- `POST /v1/jobs/{jobId}/track-selected`
- `POST /v1/extraction-runs/{runId}/track-selected`

The shared backend service validates that selected candidate IDs belong to the
job's `candidate_summary`, rejects ignored/rejected candidates, materializes the
candidate mask artifacts, reruns tracking for selected candidates only, writes
updated tracks/scene/masks/cutouts/diagnostics, and returns updated review plus
artifacts. When `exportReviewRequired` is true, selected tracks and scene
objects are marked `review_pending`; export validation blocks until review state
explicitly includes exportable tracks.

## Changed Files

- `src/motionjson/backend/selected_tracking.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/backend/api.py`
- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/backend/corrections.py`
- `tests/test_local_ui_api.py`
- `tests/test_backend_api_product.py`
- `docs/local_ui.md`
- `docs/developer_api.md`
- `docs/discovery_providers.md`
- `docs/roadmap/phase-od-04-report.md`

## Tests Run

- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export -q`
- `python3 -m pytest tests/test_backend_api_product.py::test_rest_api_track_selected_returns_review_and_blocks_unreviewed_export -q`
- `python3 -m pytest tests/test_backend_track_corrections.py::test_local_track_edit_export_inclusion_does_not_hide_track -q`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `npm run ui:layout -- --check`
- `git diff --check`

## Known Limitations

- The selected tracking implementation registers updated artifacts on the
  source discovery job rather than creating a separate child job. Newer
  artifacts with the same rel paths are used by review/export materialization.
- Review un-gating is still manual follow-up work. This phase blocks export for
  `review_pending` selected tracks but does not add the final UI control for
  explicitly approving those tracks.
- The typed run config still requires a placeholder object for discovery-first
  jobs.

## Follow-Up Tasks

- OD-05 should call `track-selected` from the candidate browser and render the
  updated API review state.
- Add an explicit review approval action that moves selected tracks from
  `review_pending` to exportable.
- Consider a child-job model for selected tracking if same-job artifact history
  becomes hard for users to understand.
