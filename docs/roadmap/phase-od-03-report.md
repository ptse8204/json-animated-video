# Phase OD-03 Report - Mock Object Discovery Provider

## Summary

Phase OD-03 adds a deterministic no-model mock provider for
`auto_object_proposals`. The provider supports clean, balanced, and
maximum-recall presets, honors candidate/object caps, writes accepted and
rejected candidate records, creates mask sequences, and writes candidate
thumbnail plus mask-preview artifacts under `discovery/`.

Review routes now resolve candidate preview artifact paths into public artifact
IDs when the generated files have been registered by the backend worker. Rejected
mock candidates stay in `candidates.json` and the API review payload, but they
are skipped when building object specs for immediate tracking.

## Changed Files

- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/pipeline_adapters.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/cli.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/candidate_review.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/backend/api.py`
- `tests/test_discovery_providers.py`
- `tests/test_local_ui_api.py`
- `docs/run_config.md`
- `docs/local_ui.md`
- `docs/discovery_providers.md`
- `docs/provider_capabilities.md`
- `docs/roadmap/phase-od-03-report.md`

## Tests Run

- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m pytest tests/test_discovery_providers.py::test_auto_object_proposals_mock_preset_is_deterministic_and_writes_artifacts tests/test_discovery_providers.py::test_auto_object_proposals_mock_maximum_recall_is_larger_and_caps_are_honored tests/test_discovery_providers.py::test_auto_object_proposals_mock_cli_writes_candidate_review_artifacts -q`
- `python3 -m pytest tests/test_discovery_providers.py::test_auto_object_proposals_cli_requires_explicit_mock_until_real_adapter tests/test_discovery_providers.py::test_initial_mask_adapter_skips_only_rejected_candidates -q`
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_auto_object_proposals_mock_review_uses_artifact_backed_candidates -q`
- `python3 -m pytest tests/test_candidate_review.py -q`
- `python3 -m pytest tests/test_backend_api_product.py::test_rest_api_job_review_returns_api_first_candidate_payload -q`
- `python3 -m pytest tests/test_discovery_providers.py -q`
- `python3 -m pytest tests/test_phase11b_automatic_object_proposals.py -q`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `git diff --check`

## Known Limitations

- The mock provider is deterministic test data, not real segmentation or
  semantic discovery.
- CLI and UI jobs must set `discovery.config.mock: true` to use this provider
  until real SAM2/SAM3 proposal adapters are implemented.
- The typed run config still requires at least one object target even for
  discovery-first UI jobs. The worker ignores that placeholder for
  `auto_object_proposals`; a later API cleanup should make discovery-only run
  configs first-class.
- Real SAM2/SAM3 proposal adapters remain capability-gated for later phases.

## Follow-Up Tasks

- OD-04 should consume accepted `candidateId` values for selected-candidate
  tracking rather than tracking mock accepted candidates immediately.
- OD-05 should update the candidate browser to render `review.candidates`
  directly and show preview artifacts from their artifact IDs.
- OD-06 should replace the mock provider with optional SAM2 automatic proposals
  when SAM2 dependencies and model paths are configured.
