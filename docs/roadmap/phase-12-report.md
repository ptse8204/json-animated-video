# Phase 12 Report - Evaluation Fixtures and Benchmarks

## Summary

Phase 12 adds a CPU-only evaluation benchmark workflow for MotionJSON. The new
`benchmark` CLI command generates small synthetic videos, writes ground-truth
masks and fixture manifests, runs extraction through no-model providers, and
emits both machine-readable `summary.json` and human-readable `summary.md`
reports.

The fixture suite includes deterministic reference cases for a red ball,
multiple objects, occlusion, a tiny object, camera motion, and a whole-frame
regression. The whole-frame fixture expects the existing track filtering logic
to reject raster-only/full-frame masks with `masks_too_large_whole_frame`.

Benchmark outputs use relative run paths and record `aiUsage: none`. The
machine-readable summary declares and validates against
`motionjson.evaluation_benchmark.v0.1`. Runtime summaries include validation
status for every object in the run, accepted/rejected tracks, fallback reason
counts, duplicate-overlap metrics, continuity, coverage, sampled frame counts,
and elapsed time. The deterministic external-mask mode is the default and is
suitable for lightweight CI; motion foreground and mock detector modes are
available as comparison paths without requiring GPU, SAM2, network access, or
heavyweight ML dependencies.

The phase started from a dirty working tree. The unrelated dirty files were
pre-existing `README.md`, `out/demo/**`, `AGENTS_old.md`, `README_old.md`, and
generated `out/demo` preview/runtime artifacts; they were left unstaged and
untouched.

## Changed Files

- `src/motionjson/benchmark.py`
- `src/motionjson/cli.py`
- `src/motionjson/schemas/__init__.py`
- `src/motionjson/schemas/motionjson.evaluation_benchmark.v0.1.schema.json`
- `tests/test_benchmark.py`
- `docs/benchmark_fixtures.md`
- `docs/codex_motionjson_quality_benchmarks.md`
- `docs/schemas.md`
- `docs/roadmap/phase-12-report.md`

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/benchmark.py src/motionjson/cli.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/benchmark.py src/motionjson/cli.py src/motionjson/schemas/__init__.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --help`
- `python -m motionjson.cli benchmark --help` failed because `python` is not
  available in this shell (`zsh:1: command not found: python`); the equivalent
  `python3` command above passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_benchmark.py -q` (`4 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k benchmark -q` (`6 passed, 212 deselected`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k "benchmark or track_filtering" -q` (`12 passed, 206 deselected`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_track_filtering.py tests/test_discovery_providers.py -q` (`18 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_benchmark.py tests/test_schema_validation.py -q` (`13 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out /tmp/motionjson-phase12-smoke --width 64 --height 48 --frames 4`
  (`2 passed, 0 regressed, 0 failed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures synthetic --modes external --out /tmp/motionjson-phase12-all-fixtures --width 64 --height 48 --frames 4`
  (`6 passed, 0 regressed, 0 failed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures synthetic --out /tmp/motionjson-phase12-default-smoke --width 64 --height 48 --frames 4 --fail-on-regression`
  (`6 passed, 0 regressed, 0 failed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` (`218 passed`)

## Known Limitations

- The benchmark suite is intentionally CPU/no-model. It measures pipeline,
  filtering, validation, and regression behavior, but it does not score real
  SAM2 or detector quality.
- External-mask mode is the deterministic reference path and default. Motion
  foreground and mock detector modes are opt-in comparison paths and may mark
  individual runs as regressed without making the command fail unless
  `--fail-on-regression` is set.
- Quality metrics are summary-level checks against expected accepted/rejected
  tracks and fallback reasons. Pixel-level IoU scoring against the ground-truth
  masks remains future work.
- Generated fixtures are compact by design for CI speed and do not replace
  larger human-reviewed demo videos.

## Follow-Up Tasks

- Add optional mask IoU/temporal stability scoring against each fixture's
  ground-truth masks.
- Add release-threshold presets once more provider modes have stable benchmark
  baselines.
- Extend documentation with benchmark examples for any future real-provider
  evaluation modes while preserving the current no-GPU default.
