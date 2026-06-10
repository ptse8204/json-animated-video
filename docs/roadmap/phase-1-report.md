---
historical: true
default_context: false
---

# Phase 1 Report - Typed Extraction Run Configuration

## Summary

Phase 1 added a dependency-light typed extraction config foundation without refactoring the extraction pipeline. The CLI now builds an `ExtractionRunConfig` at the start of `run_extract()` and then passes validated values into the existing provider and pipeline calls. The config layer is pure data: it does not import SAM2, torch, CUDA, OpenCV, providers, backend modules, or network clients.

The working tree was still not clean at the start of Phase 1 because of pre-existing `README.md`, backup files, and generated `out/demo/*` changes left unstaged from before Phase 0. Phase 1 changes were kept to config, CLI bridge, tests, docs, and this report.

## Subagent Findings

- `repo_archaeologist`: identified the current `argparse.Namespace`-driven extract surface, direct `run_pipeline()` calls, backend's smaller job config surface, and compatibility constraints for legacy extract invocation and `--mode`.
- `backend_cv_architect`: recommended stdlib dataclasses rather than Pydantic, pure serialization helpers, no provider instantiation in config parsing, and no public `--config` flag yet.
- `qa_benchmark_engineer`: confirmed the required `python -m pytest tests -k config` command fails here because `python` is unavailable, and proposed dedicated config tests because the old selector only hit SAM2 provider tests.
- `reviewer`: flagged CLI compatibility, backend provider-policy, sampling behavior, multi-object external masks, secret-free hosted config, and avoiding Phase 3 artifact work.

## Implementation

- Added `src/motionjson/config.py` with:
  - `ExtractionRunConfig`;
  - `ProjectConfig`;
  - `VideoInputConfig`;
  - `OutputConfig`;
  - `SamplingConfig`;
  - `ObjectTargetConfig`;
  - `PromptSpec`;
  - `ProviderConfig`;
  - `ThresholdProviderConfig`;
  - `ExternalMaskProviderConfig`;
  - `SAM2ProviderConfig`;
  - `MaskCacheConfig`;
  - `FilterConfig`;
  - `ExportConfig`;
  - `DebugConfig`;
  - `RightsConfig`;
  - JSON load/write helpers.
- Added `build_extraction_run_config_from_args(args)` as the current CLI bridge.
- Updated `src/motionjson/cli.py` so `run_extract()` builds typed config first and uses it when calling the existing pipeline.
- Added `tests/test_config.py` covering prompt point/box, provider selection, serialization, project config round trips, multi-object mask inputs, output settings, config errors, and CLI bridge behavior.
- Added `docs/run_config.md` and linked it from `docs/index.md`.

## Compatibility Notes

- Existing extract flags and aliases remain in place, including `--mode`, `--sam2-config`, and legacy no-subcommand extract invocation.
- `run_pipeline()` and `run_multi_object_pipeline()` signatures were not changed.
- `sample_fps <= 0` remains accepted for current source-FPS sampling compatibility.
- Config validation now fails earlier for `sam2-local` and `sam2-hosted` without a point or box prompt. This is a clearer error for an invalid run and avoids reaching provider construction without the required prompt.
- Hosted SAM2 config stores auth environment variable names only, not secret values.
- `run_config.json` is not automatically written into extraction output directories yet because artifact directory design belongs to Phase 3 and schema validation support is not added in this phase.

## Tests Run

Required command:

- `python -m pytest tests -k config` - failed because `python` is not on PATH in this shell.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k config -q` - passed, 14 tests, 112 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 126 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- Legacy no-subcommand extract invocation with threshold provider and `--max-frames 1` - passed using a temporary output directory outside the repo.
- Validation of that temporary output directory - passed.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check` - passed.

## Changed Files

- `src/motionjson/config.py`
- `src/motionjson/cli.py`
- `tests/test_config.py`
- `docs/run_config.md`
- `docs/index.md`
- `docs/roadmap/phase-1-report.md`

## Known Limitations

- Config files can be loaded/written through Python APIs, but the CLI does not yet accept a public `--config` flag.
- Config schemas are not yet packaged as JSON Schema files.
- Backend job creation still uses its existing narrower payload surface; broader shared backend/UI config integration is later work.
- Provider capability diagnostics, CUDA/model checks, and install hints are Phase 2 work.
- Structured job artifacts and automatic `run_config.json` emission are Phase 3 work.
- Provider pipeline interfaces and deterministic UI mock providers are Phase 4 work.

## Follow-Up Tasks

- Phase 2: add provider capability registry and CLI/backend diagnostics JSON output.
- Phase 3: decide when and where `run_config.json` is written as a run artifact.
- Phase 4: move provider construction toward shared provider pipeline abstractions.
- Later UI phases: use `ExtractionRunConfig` as the API contract for wizard-generated run configs.
