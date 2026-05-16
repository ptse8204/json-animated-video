# Phase 4 Report - Extraction Provider Abstraction Refactor

## Summary

Phase 4 split the current extraction flow into explicit provider-stage
contracts while preserving the public CLI and `run_pipeline()` /
`run_multi_object_pipeline()` entrypoints.

The legacy single-object path now runs through object candidate discovery,
initial mask planning, per-frame mask tracking, identity track linking,
contour vectorization, and the existing MotionJSON artifact writer. Successful
runs also write `candidates.json` and `tracks.json` as auxiliary debug
summaries for the future UI.

The working tree was still dirty at the start of Phase 4 because of
pre-existing `README.md`, backup files, and generated `out/demo/*` changes.
Phase 4 changes were kept to provider abstractions, pipeline wiring, tests,
docs, and this report.

## Subagent Findings

- `repo_archaeologist`: identified `run_pipeline()` and
  `run_multi_object_pipeline()` as the stable compatibility boundary, with
  `_extract_object()` as the mask-provider monolith to split underneath.
- `backend_cv_architect`: recommended a minimal adapter chain:
  object specs to candidates, legacy mask providers to per-frame tracks,
  identity linking, contour vectorization, and existing artifact export.
- `qa_benchmark_engineer`: required deterministic mock stage tests, existing
  single-prompt compatibility checks, and `python3` test commands because
  `python` is unavailable in this shell.
- `reviewer`: flagged CLI compatibility, optional ML imports, job event
  monotonicity, backend artifact registration, and dirty-worktree staging as
  commit risks.

## Implementation

- Added `src/motionjson/tracks.py` with provider-stage data models:
  `ObjectCandidate`, `InitialMask`, `ObjectTrack`, `TrackFrame`,
  `VideoSource`, and `RunContext`.
- Added Phase 4 provider protocols in `src/motionjson/providers/base.py`:
  `ObjectCandidateProvider`, `MaskProvider`, `VideoTracker`, `TrackLinker`,
  `Vectorizer`, and `Exporter`.
- Added staged adapters in `src/motionjson/providers/pipeline_adapters.py`:
  `ObjectSpecCandidateProvider`, `ManualPromptCandidateProvider`,
  `ObjectSpecInitialMaskProvider`, `PerFrameMaskVideoTracker`,
  `IdentityTrackLinker`, `ContourVectorizer`, and
  `MotionJSONArtifactExporter`.
- Extended `src/motionjson/providers/mocks.py` with no-model mock providers for
  every new stage.
- Updated `run_multi_object_pipeline()` to emit real
  `candidate_discovery`, `initial_masks`, `propagation`, `track_linking`, and
  `vectorization` work instead of Phase 3 skipped placeholders.
- Added `candidates.json` and `tracks.json` artifact kind detection and stale
  output cleanup.
- Added provider-pipeline docs and updated job artifact docs.

## Compatibility Notes

- Existing CLI flags, stdout summaries, root output files, and legacy aliases
  remain intact.
- Existing mask providers remain supported through adapters; SAM2 providers
  stay optional and lazily constructed by the existing CLI provider factory.
- `candidates.json` and `tracks.json` use auxiliary `format` fields and are
  skipped by `motionjson validate`.
- Backend deterministic provider policy remains unchanged; backend extraction
  still calls the shared pipeline and now registers candidate/track summaries.

## Tests Run

Required command:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest tests -k pipeline -q` - failed because `python` is not on PATH in this shell.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_provider_pipeline.py -q` - passed, 6 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k pipeline -q` - passed, 12 tests, 140 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_ai_provider_interfaces.py tests/test_provider_pipeline.py tests/test_job_artifacts.py tests/test_config.py -q` - passed, 36 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k "pipeline or provider or job" -q` - passed, 63 tests, 89 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 152 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out <tmp>/out --mask-provider mock --max-frames 2 --min-area 1` - passed and wrote `candidates.json` / `tracks.json`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate <tmp>/out` - passed.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check` - passed.

## Changed Files

- `src/motionjson/tracks.py`
- `src/motionjson/providers/base.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/providers/mocks.py`
- `src/motionjson/providers/pipeline_adapters.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/job_artifacts.py`
- `tests/test_provider_pipeline.py`
- `tests/test_ai_provider_interfaces.py`
- `tests/test_job_artifacts.py`
- `docs/provider_pipeline.md`
- `docs/job_artifacts.md`
- `docs/index.md`
- `docs/roadmap/phase-4-report.md`

## Known Limitations

- Phase 4 keeps identity linking as a no-op because dedupe, filtering, and
  multi-discovery conflict resolution are Phase 5/6 work.
- The production artifact writer still lives in `pipeline.py` for output
  compatibility. `MotionJSONArtifactExporter` exposes the interface for tests
  and future UI wiring, but does not yet own all file writes.
- Initial masks for legacy cursor-based providers are represented as provider
  plans, not consumed seed masks, so external mask sequence order remains
  compatible.
- Cancellation remains cooperative and cannot interrupt a provider call that is
  already inside OpenCV/SAM2/hosted execution.

## Follow-Up Tasks

- Phase 5: add real multi-object discovery providers that feed
  `ObjectCandidateProvider`.
- Phase 6: add object-track filtering, dedupe, and raster fallback reason
  models.
- Phase 7+: expose `candidates.json`, `tracks.json`, progress events, and
  provider diagnostics in the local UI.
