# Phase OD-02 Report - API-First Candidate Review Schema

## Summary

Phase OD-02 adds a shared API-first candidate review schema for discovery
artifacts. `candidates.json` remains the persisted artifact, but review routes
now expose normalized `review.candidates` records and aggregate
`review.candidateSummary` counts that the UI and headless clients can render
without inventing candidate state.

The local UI review response preserves the legacy `candidateSummary.provider`,
`candidateSummary.config`, `candidateSummary.video`, and
`candidateSummary.candidates` fields for current frontend compatibility. New
code should prefer `review.candidates` plus the aggregate summary fields.

The authenticated backend API now includes `GET /v1/jobs/{jobId}/review` for
candidate review clients.

## Changed Files

- `src/motionjson/candidate_review.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/backend/api.py`
- `tests/test_candidate_review.py`
- `tests/test_local_ui_api.py`
- `tests/test_backend_api_product.py`
- `docs/local_ui.md`
- `docs/developer_api.md`
- `docs/discovery_providers.md`
- `docs/roadmap/phase-od-02-report.md`

## Tests Run

- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m pytest tests/test_candidate_review.py -q`
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_review_returns_api_first_candidates_and_redacts_private_fields -q`
- `python3 -m pytest tests/test_backend_api_product.py::test_rest_api_job_review_returns_api_first_candidate_payload -q`
- `python3 -m pytest tests/test_phase11a_text_guided_discovery.py tests/test_phase11b_automatic_object_proposals.py -q`
- `python3 -m pytest tests/test_phase11c_motion_only_discovery.py tests/test_phase11d_detector_class_presets.py -q`
- `python3 -m pytest tests/test_backend_api_product.py tests/test_local_ui_api.py::test_local_ui_api_runs_mock_job_from_run_config_and_exposes_review_metadata -q`
- `python3 -m pytest tests/test_docs_links.py -q`
- `python3 -m pytest tests/test_docs_assets.py -q`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `git diff --check`

## Known Limitations

- Candidate thumbnail and mask preview artifact IDs are surfaced only when a
  provider writes those IDs into candidate metadata. OD-03/OD-06 provider work
  is expected to create real preview artifacts.
- The current frontend still renders the legacy `candidateSummary.candidates`
  list. OD-05 moves the UI to the API-first `review.candidates` list.
- `GET /v1/jobs/{jobId}/review` currently focuses on candidate review data.
  Track/correction parity with the local UI review route remains a later API
  expansion.

## Follow-Up Tasks

- OD-03 should have the mock object discovery provider write deterministic
  preview artifacts and rejected candidate metadata in this schema.
- OD-04 should consume `candidateId` values for selected-candidate tracking.
- OD-05 should update the UI candidate browser to render `review.candidates`
  directly and mark demo-only fallbacks as non-exportable.
