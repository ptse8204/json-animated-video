---
historical: true
default_context: false
---

# Phase 5 Report - Multi-Object Discovery Providers

## Summary

Phase 5 adds discovery providers that propose object candidates before mask
tracking/vectorization. The shared Phase 4 pipeline can now accept an optional
`ObjectCandidateProvider`, write `candidates.json`, adapt candidates with mask
directories into `ObjectExtractionSpec` values, and run the existing
MotionJSON writer without changing legacy single-object CLI behavior.

The working tree was still dirty at the start of Phase 5 because of
pre-existing `README.md`, backup files, and generated `out/demo/*` changes.
Phase 5 changes were kept to discovery providers, config/capability plumbing,
tests, docs, and this report.

## Subagent Findings

- `backend_cv_architect`: recommended adding discovery providers that output
  `ObjectCandidate`s, then adapting accepted candidates into existing
  `ObjectExtractionSpec`s instead of replacing the artifact writer.
- `qa_benchmark_engineer`: found that `tests -k discovery` collected no tests
  before Phase 5 and proposed focused discovery nodeids, capability checks, and
  no-GPU provider fixtures.
- `docs_devrel_engineer`: required mode guidance that explains when to use each
  discovery provider and repeats that text prompts are detector candidates, not
  raw SAM2 prompts.
- `reviewer`: found two blocking issues in staged review: manual prompt
  discovery did not yet adapt point/box candidates into mask providers, and
  heavy discovery capabilities could report runnable before a backend was
  wired. Both were fixed and the re-review found no blocking issues.

## Implementation

- Added `src/motionjson/providers/discovery.py` with:
  `ManualPromptDiscoveryProvider`, `ExternalMasksDiscoveryProvider`,
  `MotionForegroundDiscoveryProvider`, `SamAutoMasksDiscoveryProvider`,
  `TextDetectorDiscoveryProvider`, `ClassDetectorDiscoveryProvider`, provider
  schemas, and `object_specs_from_candidates()`.
- Added no-GPU usable non-manual modes:
  `motion_foreground` writes CPU frame-difference mask sequences, and
  `external_masks` imports object mask directories or manifests.
- Added mock/no-model paths for `sam_auto_masks`, `text_detector`, and
  `class_detector` that can write rectangle mask sequences for UI/test smoke
  checks.
- Added `DiscoveryConfig` to typed run config and CLI flags:
  `--discovery-provider`, `--discovery-config`, `--discovery-text`,
  `--discovery-class`, `--discovery-max-candidates`, and
  `--discovery-min-area`.
- Updated provider diagnostics with discovery capability entries and optional
  heavy-provider warnings.
- Updated job artifact cleanup/manifest behavior for generated `discovery/`
  assets.
- Added discovery docs and linked them from the docs index.

## Compatibility Notes

- Existing `--mask-provider`, `--object-mask-dir`, single prompt, and legacy
  output paths remain supported.
- Discovery mode is separate from mask provider selection in the typed run
  config.
- Heavy providers do not import SAM2, torch, detector packages, or network
  clients at module import time.
- `text_detector` records candidate output first and explicitly does not route
  text directly to raw SAM2.

## Tests Run

Required command:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest tests -k discovery -q` - failed because `python` is not on PATH in this shell.

Equivalent and additional verification:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k discovery -q` - passed, 19 tests, 152 deselected.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_config.py tests/test_capabilities.py tests/test_provider_pipeline.py tests/test_job_artifacts.py -q` - passed, 57 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 171 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed and listed discovery flags.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json` - passed and listed discovery provider capabilities.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out <tmp>/out --discovery-provider motion_foreground --discovery-min-area 4 --discovery-max-candidates 2 --max-frames 3 --min-area 1` - passed and wrote `candidates.json` plus `discovery/motion_foreground/`.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate <tmp>/out --object-id motion_0` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out <tmp>/out --discovery-provider text_detector --discovery-text "red ball . hand" --discovery-config '{"mock":true}' --discovery-max-candidates 2 --max-frames 2 --min-area 1` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate <tmp>/out --object-id text_detector_red_ball` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out <tmp>/out --discovery-provider manual_prompt --mask-provider mock --prompt-box 10,10,20,20 --max-frames 2 --min-area 1` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate <tmp>/out` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out <tmp>/out --discovery-provider manual_prompt --prompt-box 10,10,20,20 --max-frames 2 --min-area 1` - passed with the default threshold mask provider.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli validate <tmp>/out` - passed.
- `npm test` - passed, 18 Node tests.
- `npm run lint` - passed.
- `git diff --check -- <phase-5-files>` - passed.

## Changed Files

- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/cli.py`
- `src/motionjson/config.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/job_artifacts.py`
- `tests/test_discovery_providers.py`
- `tests/test_config.py`
- `tests/test_capabilities.py`
- `docs/discovery_providers.md`
- `docs/provider_capabilities.md`
- `docs/provider_pipeline.md`
- `docs/run_config.md`
- `docs/job_artifacts.md`
- `docs/index.md`
- `docs/roadmap/phase-5-report.md`

## Known Limitations

- `motion_foreground` is a simple CPU frame-difference proposal source. It can
  produce rough blobs and background fragments; Phase 6 filtering/dedupe will
  harden this.
- `sam_auto_masks`, `text_detector`, and `class_detector` are scaffolded for
  optional real backends. Mock mode is intentionally local and deterministic.
- Candidate-to-spec adaptation currently requires `metadata.maskDir` or an
  explicit mask-provider factory. Box-only real detector candidates still need a
  configured segmenter/tracker before production export.
- Track dedupe, whole-frame rejection, and raster fallback reason codes remain
  Phase 6 work.

## Follow-Up Tasks

- Phase 6: add filtering/dedupe and fallback diagnostics for noisy discovery
  outputs.
- Phase 7+: expose capability entries, discovery schemas, `candidates.json`,
  and generated discovery artifacts in the local UI.
