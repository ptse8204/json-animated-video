# Phase 11C Report: Motion-Only Discovery Workflow

Date: 2026-05-17

## Summary

Phase 11C wires the CPU/no-model `motion_foreground` workflow through the
local UI worker. `Find moving objects` can now start a local job that uses
frame-difference/background-subtraction style motion candidates, writes
generated masks under `discovery/motion_foreground/`, adapts them into object
tracks, and exposes candidate summaries, fallback diagnostics, and track review
metadata before export.

Motion candidate scores now propagate into `tracks.json` as track confidence,
so UI review and benchmark artifacts can show confidence for motion-only
results. The backend extraction policy now treats `motion` as a deterministic
local provider alongside `mock`, `threshold`, and `external`.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md` and
`docs/Codex Prompt Instrcution.md` were preexisting untracked docs. They were
not staged for this phase.

## Changed Files

- `src/motionjson/backend/models.py`
  - Allows the deterministic local `motion` provider in backend extraction
    policy.
- `src/motionjson/backend/worker.py`
  - Routes `motion_foreground` discovery configs through
    `run_multi_object_pipeline` and constructs `MotionMaskProvider` for
    direct `motion` jobs.
- `src/motionjson/providers/pipeline_adapters.py`
  - Carries candidate scores into initial masks and object-track confidence.
- `tests/test_phase11c_motion_only_discovery.py`
  - Adds provider and local UI worker tests for motion candidates, public
    review payloads, confidence, and path redaction.
- `tests/test_benchmark.py`
  - Adds benchmark coverage that motion mode records candidate-derived track
    confidence.
- `docs/discovery_providers.md`
  - Documents local UI and CLI motion foreground behavior.
- `docs/local_ui.md`
  - Documents `Find moving objects` as a runnable CPU/no-model worker path.
- `docs/benchmark_fixtures.md`
  - Documents candidate-derived confidence in benchmark reports.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase11c_motion_only_discovery.py -q`
  - Result: 2 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_benchmark.py::test_benchmark_motion_foreground_mode_records_candidate_confidence tests/test_benchmark.py::test_benchmark_name_normalizers_support_documented_aliases -q`
  - Result: 2 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py::test_local_ui_run_config_validation_uses_existing_config_code_and_warns tests/test_phase8_ui_config_builder.py -q`
  - Result: 5 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-11c-motion --discovery-provider motion_foreground --discovery-config '{"threshold": 8, "min_area": 1, "max_candidates": 2, "morph_open": 1, "morph_close": 3}' --mask-provider motion --max-frames 4 --min-area 1`
  - Result: passed; wrote motion candidates, tracks, and MotionJSON outputs.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures red_ball --modes motion --out /tmp/motionjson-11c-bench --width 64 --height 48 --frames 4 --min-area 1`
  - Result: passed; wrote `summary.json` and `summary.md`, with the heuristic
    comparison run marked regressed as expected for the fixture.
- `node scripts/test_ui_config_builder.mjs`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_phase11a_text_guided_discovery.py tests/test_phase11b_automatic_object_proposals.py tests/test_phase11c_motion_only_discovery.py tests/test_benchmark.py tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py tests/test_phase9_ui_job_review_smoke.py tests/test_capabilities.py -q`
  - Result: 75 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_docs_links.py tests/test_phase11c_motion_only_discovery.py -q`
  - Result: 6 passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q`
  - Result: 271 passed.

## Screenshots And Demos Produced

No screenshots were produced. The phase produced temporary local artifacts
under `/tmp/motionjson-11c-motion` and `/tmp/motionjson-11c-bench`; these were
not committed.

## Review

The implementation uses the existing CPU frame-difference discovery provider
instead of adding heavy optical-flow or ML dependencies. It preserves provider
diagnostics, keeps generated output local, and adds tests for public API
redaction and confidence propagation.

## Known Limitations

- `motion_foreground` is a simple CPU heuristic. Camera movement, shadows, and
  low-contrast motion can produce extra fragments or miss objects.
- Confidence is currently candidate-derived from motion area, not a calibrated
  model confidence.
- Optical flow and richer background modeling remain future improvements.

## Follow-Up Tasks

- Add UI affordances to tune motion sensitivity with quick preview frames.
- Add optional optical-flow/background-model providers behind capability
  checks.
- Continue Phase 11D with detector class presets.
