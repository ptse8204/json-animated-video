# Phase OD-01 Report: Object Discovery Quality Presets

## Summary

Phase OD-01 adds API-addressable object discovery quality presets to typed run
configuration. `auto_object_proposals` is now a valid discovery mode with a
normalized config contract for:

- `clean`
- `balanced`
- `maximum_recall`
- `trace_everything`

The clean preset is the low-cost default. Clean, balanced, and maximum recall
default `trackSelectedOnly` to `true`. Trace Everything is explicit,
review-gated, and requires `costWarningAcknowledged: true` before the typed
config validates.

The implementation remains capability-gated. Real automatic proposal adapters
are not claimed as runnable yet; mock routing is available for smoke checks.

## Starting Working Tree

The working tree still had the same pre-existing untracked prompt/context
files before OD-01:

- `docs/codex/motionjson_codex_prompt_api_first_object_discovery_sam2_sam3.md`
- `docs/codex/motionjson_sam2_sam3_decision_notes.md`

## Changed Files

- `src/motionjson/config.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/cli.py`
- `src/motionjson/backend/worker.py`
- `tests/test_config.py`
- `tests/test_discovery_providers.py`
- `tests/test_capabilities.py`
- `tests/test_cli_ui.py`
- `tests/test_local_ui_api.py`
- `docs/run_config.md`
- `docs/discovery_providers.md`
- `docs/provider_capabilities.md`
- `docs/local_ui.md`
- `docs/roadmap/phase-od-01-report.md`

## Implementation Notes

- Added `auto_object_proposals` to typed discovery modes, CLI discovery
  choices, provider schemas, capabilities, and local UI run-config defaults.
- Added preset defaults and validation in `DiscoveryConfig` for clean,
  balanced, maximum recall, and Trace Everything.
- Normalized `auto_object_proposals` config to camelCase fields while accepting
  snake_case aliases such as `quality_preset`, `max_candidates`, and
  `track_selected_only`.
- Added field-level validation for keyframe/candidate caps and ratios.
- Added Trace Everything warning acknowledgement validation.
- Added capability diagnostics for `auto_object_proposals` as a scaffolded,
  mock-available discovery surface rather than a runnable real model provider.
- Added mock worker/CLI routing through the existing automatic-mask scaffold
  under the `auto_object_proposals` provider name.

## Risk Review

A read-only OD-01 scout reviewed the typed config, provider schema, CLI bridge,
local UI defaults, worker routing, docs, and tests. The scout called out the
main risks: freeform config needed a typed normalizer, camelCase/snake_case
aliases needed explicit handling, Trace Everything needed a validation home,
candidate caps needed typed-config validation, and duplicated registries needed
to be updated together. Those risks are addressed in this phase except full
selected-only tracking semantics, which belong to OD-04.

## Tests And Validation Run

- `python3 -m pytest tests/test_config.py tests/test_discovery_providers.py tests/test_capabilities.py tests/test_cli_ui.py -q` passed: 65 tests.
- `python3 -m pytest tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public -q` passed.
- `python3 -m pytest -q` passed: 319 tests.
- `npm test` passed: 19 tests.
- `npm run lint` passed.
- `npm run build` passed.
- `python3 -m motionjson.cli --help` passed.
- `python3 -m motionjson.cli extract --help` passed.
- `python3 -m motionjson.cli backend --help` passed.
- `python3 -m motionjson.cli ui --help` passed.
- `python3 -m motionjson.cli benchmark --help` passed.
- `python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-od01-auto-mock --discovery-provider auto_object_proposals --discovery-config '{"mock": true, "qualityPreset": "clean"}' --discovery-max-candidates 2 --mask-provider mock --max-frames 2 --min-area 1` passed.
- `python3 -m motionjson.cli validate /tmp/motionjson-od01-auto-mock --object-id auto_object_proposals_Visible_segment_1` passed.

## Known Limitations

- `trackSelectedOnly` is now validated and defaulted, but selected-candidate
  tracking is not implemented until OD-04.
- Candidate review payloads still use the current `candidates.json` summary
  shape until OD-02.
- The mock routing path can run `auto_object_proposals`, but clean versus
  maximum-recall candidate-count behavior is not implemented until OD-03.
- Real SAM2 automatic proposals remain optional and capability-gated until
  OD-06.
- SAM3 diagnostics and provider modes are not implemented until OD-07 and
  later.
- Trace Everything has typed warning acknowledgement now, but the full expert
  UI and export safety gates are later OD phases.

## Follow-Up Tasks

- OD-02: add the API-first candidate review schema and summary.
- OD-03: make the mock `auto_object_proposals` provider emit deterministic
  candidate artifacts, rejected candidates, and preset-sensitive counts.
- OD-04: implement selected-candidate tracking APIs and enforce selected-only
  execution.
- OD-05: update the UI to render API candidates only for normal completed job
  results.
