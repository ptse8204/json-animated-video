---
historical: true
default_context: false
---

# Phase 11D Report: Detector Class Presets

Date: 2026-05-17

## Summary

Phase 11D adds a mock/no-model known-class detector workflow. Users can choose
`Find known classes` in the local UI, select a class preset such as
`common_objects` or `vehicles`, add custom class labels, and run a local mock
job that writes class-detector candidates, generated mask sequences, tracks,
fallback diagnostics, and export review metadata.

The CLI now accepts `--discovery-class-preset` for
`--discovery-provider class_detector`, and benchmark mode `class` maps to the
new `class_detector_mock` comparison path. Real YOLO/known-class detector
execution remains optional and capability-gated; diagnostics still report
missing `ultralytics` or model paths instead of pretending the backend is
available.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md` and
`docs/Codex Prompt Instrcution.md` were preexisting untracked docs. They were
not staged for this phase.

## Changed Files

- `src/motionjson/providers/discovery.py`
  - Adds class-detector presets, provider schema metadata, preset expansion,
    confidence-threshold validation, and normalized detector handoff config.
- `src/motionjson/backend/worker.py`
  - Routes local UI `class_detector` mock jobs through the shared multi-object
    provider pipeline.
- `src/motionjson/cli.py`, `src/motionjson/config.py`
  - Add and round-trip `--discovery-class-preset`.
- `src/motionjson/benchmark.py`,
  `src/motionjson/schemas/motionjson.evaluation_benchmark.v0.1.schema.json`
  - Add `class_detector_mock` and documented aliases such as `class`.
- `src/motionjson/ui/static/*`
  - Adds the `Find known classes` preset, class preset selector, class-list
    config, capability visibility, and local run gating updates.
- `tests/test_phase11d_detector_class_presets.py`
  - Covers provider presets, local UI mock success, real-path failure
    diagnostics, public artifact redaction, and static UI controls.
- `tests/test_discovery_providers.py`, `tests/test_benchmark.py`,
  `tests/test_config.py`, `tests/test_cli_ui.py`,
  `tests/test_phase8_ui_config_builder.py`, `scripts/test_ui_config_builder.mjs`
  - Add class preset coverage across provider, CLI/config, benchmark, and UI
    contract paths.
- `docs/assets/*.png`
  - Regenerates local UI screenshots so the wizard and diagnostics images
    match the updated UI.
- `docs/discovery_providers.md`, `docs/local_ui.md`,
  `docs/benchmark_fixtures.md`, `docs/run_config.md`,
  `docs/provider_capabilities.md`, `docs/first_run.md`,
  `docs/troubleshooting.md`
  - Document class presets, mock/local behavior, benchmark aliases, and real
    detector limitations.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_phase11d_detector_class_presets.py tests/test_benchmark.py::test_benchmark_name_normalizers_support_documented_aliases tests/test_benchmark.py::test_benchmark_class_detector_mock_mode_writes_preset_candidate_review_fixture tests/test_config.py::test_discovery_config_round_trips_class_detector_preset_and_classes tests/test_cli_ui.py::test_extract_help_documents_discovery_modes_and_flags -q`
  - Result: 26 passed.
- `node scripts/test_ui_config_builder.mjs`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase8_ui_config_builder.py -q`
  - Result: 5 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-11d-class --discovery-provider class_detector --discovery-class-preset vehicles --discovery-class forklift --discovery-config '{"mock":true,"confidence_threshold":0.4}' --discovery-max-candidates 3 --mask-provider mock --max-frames 2 --min-area 1`
  - Result: passed; wrote class-detector candidates, tracks, and MotionJSON
    outputs.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures multi_object --modes class --out /tmp/motionjson-11d-bench --width 64 --height 48 --frames 4 --min-area 1`
  - Result: passed; wrote `summary.json` and `summary.md`, with the comparison
    run marked regressed as expected for the mock heuristic.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_phase11a_text_guided_discovery.py tests/test_phase11b_automatic_object_proposals.py tests/test_phase11c_motion_only_discovery.py tests/test_phase11d_detector_class_presets.py tests/test_benchmark.py tests/test_config.py tests/test_cli_ui.py tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py tests/test_phase9_ui_job_review_smoke.py tests/test_capabilities.py -q`
  - Result: 105 passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 scripts/capture_docs_assets.py`
  - Result: passed; regenerated local UI screenshots and red-ball docs assets.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_docs_assets.py -q`
  - Result: 4 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py tests/test_phase11d_detector_class_presets.py -q`
  - Result: 12 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q`
  - Result: 283 passed.
- `git diff --check`
  - Result: passed.

## Browser Smoke

Started `python3 -m motionjson.cli ui --host 127.0.0.1 --port 8765 --no-open
--mock` and opened `http://127.0.0.1:8765/ui/` in the in-app browser. The
`Find known classes` preset was visible, selecting it showed class preset and
class-list controls, and the config preview contained `discovery.mode:
class_detector`, `class_preset: common_objects`, `mock: true`, and provider
`mock`.

## Known Limitations

- Real YOLO/known-class detector execution is still scaffolded. The provider
  supports injected detectors, but no concrete Ultralytics adapter is wired in
  this phase.
- Mock class boxes are deterministic rectangles for UI/test review; they are
  not semantic detections.
- Preset classes are intentionally small starter sets and should be expanded
  when a real detector backend exposes its supported label set.

## Follow-Up Tasks

- Add a concrete YOLO/Ultralytics adapter behind the existing capability
  checks.
- Surface detector-supported labels dynamically when a real backend is
  configured.
- Continue Phase 11E with export quality routing.
