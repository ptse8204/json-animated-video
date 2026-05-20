# Phase OD-11 Report - Discovery Metadata Schema

## Summary

Phase OD-11 makes discovered and selected candidates first-class MotionJSON
metadata. Generated scene objects, raster layers, object manifests, object
motion files, web manifests, and track summaries now carry a stable
`discovery` block with candidate source, provider/model, preset, scores,
review state, selected-tracking state, export review status, artifact
references, rights/source lineage, and correction-history reference slots.

The core schemas accept the new optional block while preserving older outputs
that do not contain discovery metadata. The block allows additive future fields
so runtimes can ignore unknown provider-specific metadata without breaking
validation. `@motionjson/runtime` preserves discovery metadata on normalized
objects, and `@motionjson/sdk` adds helpers for parsing candidate and MotionJSON
discovery metadata.

## Changed Files

- `src/motionjson/pipeline.py`
  - Builds and writes the canonical `discovery` block from candidate, initial
    mask, track, quality, and rights data.
- `src/motionjson/providers/discovery.py`
  - Carries candidate metadata into `ObjectExtractionSpec` and preserves
    selected-candidate source/score metadata through external mask imports.
- `src/motionjson/backend/selected_tracking.py`
  - Preserves original candidate review metadata during selected tracking and
    updates object-level discovery review state when export review is required.
- `src/motionjson/backend/export_workflows.py`
  - Treats `discovery.reviewRequired` and discovery export statuses as export
    gates.
- `src/motionjson/exporters/web_manifest.py`
  - Copies object discovery metadata into web asset manifests.
- `src/motionjson/schemas/*.schema.json`
  - Adds optional `discovery`, `exportStatus`, and `exportIncluded` fields to
    scene, object manifest, object motion, and web manifest contracts.
- `packages/motionjson-runtime/src/manifest.js`
  - Preserves discovery metadata during normalization without interpreting
    unknown future fields.
- `packages/motionjson-sdk/src/index.js`
  - Adds `normalizeDiscoveryMetadata`, `discoveryMetadataFromCandidate`, and
    `discoveryMetadataFromMotionJSON`.
- `tests/test_schema_validation.py`, runtime tests, and SDK tests
  - Cover schema validation, backward compatibility, future fields, runtime
    normalization, and SDK parsing.
- `README.md`, `docs/discovery_providers.md`, `docs/schemas.md`
  - Documents the new MotionJSON discovery metadata contract.

## Tests Run

- `python3 -m py_compile src/motionjson/pipeline.py src/motionjson/providers/discovery.py src/motionjson/backend/selected_tracking.py src/motionjson/backend/export_workflows.py src/motionjson/exporters/web_manifest.py tests/test_schema_validation.py`
- `python3 -m pytest tests/test_schema_validation.py -q`
- `python3 -m pytest tests/test_discovery_providers.py tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export tests/test_backend_api_product.py::test_rest_api_track_selected_returns_review_and_blocks_unreviewed_export tests/test_final_export.py tests/test_schema_validation.py -q`
- `python3 -m pytest tests/test_backend_api_product.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_job_artifacts.py tests/test_quality_engine.py -q`
- `python3 -m pytest -q`
- `npm test --workspace packages/motionjson-runtime`
- `npm test --workspace packages/motionjson-sdk`
- `npm test`
- `npm run lint`
- `npm run build`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m motionjson.cli backend diagnostics --json`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Risk Review

The requested read-only `test-gap-scout` could not be spawned because the
Codex environment reported `agent thread limit reached`. The master agent
performed the test-gap review in-thread. Coverage now includes:

- schema validation with new discovery metadata across core artifacts;
- backward compatibility after removing the optional `discovery` fields;
- additive future fields inside discovery metadata;
- runtime normalization preserving unknown fields;
- SDK parsing of candidate/review metadata;
- selected-candidate review gating and export blocking;
- export workflow gating from discovery review state.

## Known Limitations

- `correctionHistoryRef` is schema-supported and emitted as `null` unless a
  caller/provider supplies a concrete review-state reference.
- Discovery review approval still uses the existing correction/export state
  machinery. A later phase should add an explicit reviewed/approved transition
  that clears `discovery.reviewRequired` after user review.

## Follow-up Tasks

- Wire correction history events back into `discovery.correctionHistoryRef`
  when review-state manifests are materialized.
- Extend the local UI track approval workflow so users can explicitly mark
  selected auto-discovered objects as reviewed for export.
