# Phase 11B Report: Automatic Object Proposal Workflow

Date: 2026-05-17

## Summary

Phase 11B makes the CPU/mock automatic object proposal workflow runnable from
the local UI worker and benchmark harness. `sam_auto_masks` mock mode now
generates multiple deterministic visible-segment candidates, writes generated
mask sequences under `discovery/sam_auto_masks/`, adapts those candidates into
object specs, and runs the shared candidate -> mask -> track -> filter/dedupe
-> review pipeline.

The local UI worker now supports mock `sam_auto_masks` alongside the Phase 11A
mock `text_detector` route. It still refuses non-mock automatic proposal runs
with `failure_diagnostics` instead of silently pretending that SAM/SAM2
automatic masks are available. Candidate review copy is now discovery-neutral,
so the Candidates panel works for text and automatic proposals.

Benchmark mode `auto`/`sam_auto_masks_mock` was added as a CPU-only comparison
path. It is expected to produce comparison regressions on semantic fixtures
because deterministic mock boxes are not ground-truth labels; the value is
repeatable artifact and review-regression coverage without GPU/model downloads.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md` and
`docs/Codex Prompt Instrcution.md` were preexisting untracked docs. They were
not staged for this phase.

## Changed Files

- `src/motionjson/providers/discovery.py`
  - Makes `sam_auto_masks` mock mode emit multiple visible-segment candidates
    based on `max_candidates`.
- `src/motionjson/backend/worker.py`
  - Routes mock `sam_auto_masks` run configs through
    `run_multi_object_pipeline` and keeps non-mock discovery adapters
    capability-gated.
- `src/motionjson/ui/static/config_builder.js`
  - Marks generated automatic-proposal configs as `mock: true` for no-model
    UI smoke runs.
- `src/motionjson/ui/static/app.js`
  - Makes candidate-review empty-state copy apply to all discovery providers.
- `src/motionjson/benchmark.py`
  - Adds `sam_auto_mock` benchmark mode plus `auto` and
    `sam_auto_masks_mock` aliases.
- `src/motionjson/schemas/motionjson.evaluation_benchmark.v0.1.schema.json`
  - Allows `sam_auto_mock` in benchmark summary and run mode enums.
- `scripts/test_ui_config_builder.mjs`
  - Locks `sam_auto_masks` UI configs to mock mode.
- `tests/test_phase11b_automatic_object_proposals.py`
  - Adds provider, local UI worker, review-artifact, and failure-diagnostics
    coverage for automatic proposal mock runs.
- `tests/test_phase11a_text_guided_discovery.py`
  - Updates candidate panel copy and generalized discovery failure message
    assertions after the worker helper was shared with Phase 11B.
- `tests/test_benchmark.py`
  - Adds benchmark alias, schema validation, and `sam_auto_mock` artifact
    coverage.
- `docs/discovery_providers.md`
  - Documents local UI and CLI automatic proposal mock smoke paths.
- `docs/local_ui.md`
  - Documents automatic proposal review behavior and remaining real-backend
    gating.
- `docs/benchmark_fixtures.md`
  - Documents `auto` benchmark comparison mode.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase11b_automatic_object_proposals.py -q`
  - Result: 3 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_benchmark.py::test_benchmark_name_normalizers_support_documented_aliases tests/test_benchmark.py::test_benchmark_sam_auto_mock_mode_writes_candidate_review_fixture -q`
  - Result: 2 passed.
- `python3 -m json.tool src/motionjson/schemas/motionjson.evaluation_benchmark.v0.1.schema.json`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_phase11a_text_guided_discovery.py tests/test_phase11b_automatic_object_proposals.py tests/test_benchmark.py tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py tests/test_phase9_ui_job_review_smoke.py tests/test_capabilities.py -q`
  - Result: 72 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_docs_links.py tests/test_phase11a_text_guided_discovery.py tests/test_phase11b_automatic_object_proposals.py tests/test_benchmark.py -q`
  - Result: 18 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-11b-auto-mock --discovery-provider sam_auto_masks --discovery-config '{"mock": true, "keyframes": [0], "max_candidates": 3}' --mask-provider mock --max-frames 2 --min-area 1`
  - Result: passed; wrote three automatic-proposal object tracks and
    MotionJSON outputs.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures multi_object --modes auto --out /tmp/motionjson-11b-bench --width 64 --height 48 --frames 4 --min-area 1`
  - Result: passed; wrote `summary.json` and `summary.md`, with the mock
    comparison run marked regressed as expected for non-semantic mock boxes.
    The generated `summary.json` validates against the packaged benchmark
    schema.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures multi_object --modes sam_auto_masks_mock --out /tmp/motionjson-11b-bench-alias --width 64 --height 48 --frames 4 --min-area 1`
  - Result: passed; verified the documented alias.
- `node scripts/test_ui_config_builder.mjs`
  - Result: passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q`
  - Result: 268 passed.

## Screenshots And Demos Produced

No screenshots were produced. The phase produced temporary local artifacts
under `/tmp/motionjson-11b-auto-mock` and `/tmp/motionjson-11b-bench`; these
were not committed.

## Review

A bounded read-only scout confirmed the preexisting gap: `sam_auto_masks` had
CLI/provider scaffolding and UI config generation, while the local UI worker
rejected it. The implemented slice follows the scout recommendation: route only
mock automatic proposal configs through the shared pipeline, add UI/review
tests, add benchmark comparison mode, and document that real automatic mask
generation remains a later optional-backend task.

## Known Limitations

- Mock automatic proposals are deterministic rectangular masks. They preserve
  keyframe/filter config for review but do not implement real stability
  scoring, background rejection, or SAM/SAM2 automatic mask generation.
- Benchmark `auto` mode is a comparison/regression tool, not a semantic
  quality baseline.
- Candidate review is still post-run; a pre-tracking accept/reject proposal
  gate remains future work.

## Follow-Up Tasks

- Wire a real automatic mask backend behind explicit capability checks and
  model/device diagnostics.
- Add pre-run candidate accept/reject controls once proposal-only jobs exist.
- Continue Phase 11C with motion-only discovery confidence and UI routing.
