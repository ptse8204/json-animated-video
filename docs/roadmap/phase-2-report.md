# Phase 2 Report - Provider Capability Registry And Diagnostics

## Summary

Phase 2 added a dependency-light provider capability registry and a backend CLI
diagnostics command. The registry reports local environment readiness, optional
provider availability, CUDA status, FFmpeg status, video IO checks, output path
writability, install hints, no-model safety, mock availability, and planned
provider surfaces as JSON.

The working tree was still not clean at the start of Phase 2 because of
pre-existing `README.md`, backup files, and generated `out/demo/*` changes left
unstaged from before Phase 0. Phase 2 changes were kept to provider
diagnostics, backend CLI wiring, tests, docs, and this report.

## Subagent Findings

- `backend_cv_architect`: recommended a standalone `motionjson.capabilities`
  module that avoids eager provider instantiation, checks `threshold`,
  `motion`, `external`, `mock`, legacy `sam2`, `sam2-local`, `sam2-hosted`,
  detector/tracker placeholders, vector/export surfaces, CUDA, FFmpeg, video
  IO, and output writability.
- `qa_benchmark_engineer`: recommended `tests/test_capabilities.py` with
  mocked missing optional providers, CLI JSON parsing, no backend DB/storage
  initialization, FFmpeg absence, video/output probes, and secret redaction.
- `docs_devrel_engineer`: recommended a dedicated provider diagnostics page and
  cross-links from run config, SAM2, provider architecture, and backend docs.
- `reviewer`: flagged risks around preserving backend provider policy, keeping
  OpenRouter out of segmentation, retaining a diagnostic entry for the legacy
  `sam2` stub, avoiding secret output, and ensuring diagnostics run before
  backend database initialization.

## Implementation

- Added `src/motionjson/capabilities.py` with:
  - `DependencyStatus`;
  - `ProviderCapability`;
  - `build_capability_report()`;
  - `capability_report_json()`;
  - dependency, CUDA, FFmpeg, video IO, and output checks;
  - provider entries for no-model providers, SAM2 paths, hosted/reasoning
    providers, planned detector/tracker surfaces, vectorization, and exporters.
- Added `python -m motionjson.cli backend diagnostics --json`.
- Added optional `--video`, `--output-dir`, `--sam2-checkpoint`, and
  `--sam2-config` probes to diagnostics.
- Kept diagnostics ahead of backend `_open()` so it does not initialize SQLite
  or storage directories.
- Added `tests/test_capabilities.py`.
- Added `docs/provider_capabilities.md` and linked it from relevant docs.

## Compatibility Notes

- Existing CLI extraction and backend job behavior is unchanged.
- Heavy providers remain optional. Missing SAM2, torch, CUDA, hosted
  credentials, OpenRouter credentials, or FFmpeg are reported as diagnostics
  instead of being required by the base CLI. SAM2 is not imported by
  diagnostics; torch is queried only for CUDA status when it is installed.
- The legacy `sam2` provider remains represented as an unavailable compatibility
  stub; explicit `sam2-local` and `sam2-hosted` entries provide actionable
  readiness details.
- OpenRouter is reported as an optional reasoning provider only and is not
  accepted as a segmentation provider.
- Hosted provider checks report environment-variable presence only; token values
  are not printed.
- Explicit diagnostics `--sam2-checkpoint` and `--sam2-config` values take
  precedence over `SAM2_LOCAL_CHECKPOINT` and `SAM2_LOCAL_CONFIG`, matching the
  existing extraction CLI configuration path.

## Review Findings Addressed

- Unrelated `README.md`, generated `out/demo/*`, and backup files are still
  intentionally excluded from the Phase 2 staging set.
- Added diagnostics flags and tests for explicit SAM2 checkpoint/config paths.
- Normalized dependency `installHint` JSON keys to match provider diagnostics.

## Tests Run

Required commands:

- `python -m motionjson.cli backend --help` - failed because `python` is not on
  PATH in this shell.
- `python -m pytest tests -k capability` - documented unavailable for the same
  `python` executable reason; the `python3` equivalent passed.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed and listed `diagnostics`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --help` - passed and listed `--sam2-checkpoint` / `--sam2-config`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json` - passed and emitted parseable `motionjson.provider_diagnostics.v0.1` JSON.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json --sam2-checkpoint <missing temp checkpoint> --sam2-config <missing temp config>` - passed and reported explicit argument-sourced SAM2 model diagnostics.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json --video examples/demo_red_ball.mp4 --output-dir <temporary output directory outside repo>` - passed; video and output probes reported checked/readable/writable.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k capability -q` - passed, 8 tests, 127 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_capabilities.py -q` - passed, 9 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 135 tests.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check` - passed.

## Changed Files

- `src/motionjson/capabilities.py`
- `src/motionjson/backend/cli.py`
- `tests/test_capabilities.py`
- `docs/provider_capabilities.md`
- `docs/index.md`
- `docs/run_config.md`
- `docs/sam2_segmentation.md`
- `docs/ai_provider_architecture.md`
- `docs/saas_backend.md`
- `docs/roadmap/phase-2-report.md`

## Known Limitations

- Diagnostics are read-only preflight data; they do not yet feed a UI because
  the API/UI phases are later in the roadmap.
- Detector, class detector, video tracker, and track linker entries are planned
  placeholders until provider pipeline phases implement them.
- `sam2-local` readiness can confirm package/model/config availability, but it
  does not instantiate SAM2 or validate a checkpoint by running inference.
- FFmpeg is checked by PATH lookup only. Exporter runtime errors are still
  handled by the existing exporter code paths.
- The diagnostics command emits JSON by default; a human-readable text summary
  can be added later if useful, but the Phase 2 acceptance criteria require a
  machine-readable output.

## Follow-Up Tasks

- Phase 3: use capability diagnostics in structured job failure/preflight
  artifacts.
- Phase 4: connect these provider names to the provider pipeline abstractions.
- Phase 5: replace discovery placeholders with concrete no-model and optional
  detector providers.
- Phase 7 and later UI phases: surface capability statuses before a run and
  disable unavailable workflows with visible reasons.
