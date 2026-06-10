---
historical: true
default_context: false
---

# Phase OD-06 Report: Optional SAM2 Automatic Proposal Adapter

## Summary

Implemented an optional, capability-gated SAM2 automatic proposal path for `auto_object_proposals` and `sam_auto_masks`.

The new path keeps SAM2/torch out of the base install, lazy-imports SAM2 automatic mask generation only after checkpoint/config paths are supplied, samples keyframes from discovery config, filters/dedupes proposals, writes API-first candidate artifacts, and prepares accepted candidates as mask sequences for selected tracking. Mock/no-model discovery remains the safe default.

## Changed Files

- `README.md`
- `docs/discovery_providers.md`
- `docs/provider_capabilities.md`
- `docs/provider_pipeline.md`
- `docs/repo_status.md`
- `docs/run_config.md`
- `docs/sam2_segmentation.md`
- `docs/roadmap/phase-od-06-report.md`
- `scripts/smoke_embed_examples.mjs`
- `src/motionjson/backend/worker.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/cli.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/sam2.py`
- `tests/test_backend_jobs_worker.py`
- `tests/test_capabilities.py`
- `tests/test_discovery_providers.py`
- `tests/test_docs_links.py`
- `tests/test_phase11b_automatic_object_proposals.py`
- `tests/test_sam2_providers.py`

## Tests Run

- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Known Limitations

- CI uses fake SAM2 proposal and propagation backends; no real SAM2 checkpoint, GPU, or model execution was run in this phase.
- The real SAM2 automatic proposal adapter assumes a SAM2 package exposing `sam2.automatic_mask_generator.SAM2AutomaticMaskGenerator` and `sam2.build_sam.build_sam2`; unsupported SAM2 package layouts fail clearly instead of being treated as runnable.
- If an injected automatic proposal backend has no propagation hook, accepted candidates are written as keyframe-seed mask sequences with an explicit warning.
- SAM3 concept/exemplar discovery and hosted SAM3 remain later phases.

## Follow-Up Tasks

- Add optional real-environment SAM2 smoke documentation once a supported checkpoint/config fixture is available.
- Expand selected-candidate tracking to call provider-specific propagation at track-selected time when a live SAM2 session is available.
- Add SAM3 provider diagnostics and mocks in OD-07.
