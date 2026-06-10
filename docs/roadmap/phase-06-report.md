---
historical: true
default_context: false
---

# Phase 06 Report: Provider Integrations And Fallback Coverage

Date: 2026-05-17

## Summary

Phase 06 made provider readiness easier to reason about without changing the
existing diagnostics schema id or removing legacy fields. Provider capability
records now expose explicit `installed`, `configured`, `runnable`,
`needsCredentials`, `needsGpu`, `needsModelPath`, `modelPaths`, and
`estimatedCost` fields. Local/free providers report zero local cost when they
are runnable. Hosted/network providers report unknown provider cost and
credentials/network requirements.

The local UI now renders those fields as provider chips, warns when a provider
is configured but not runnable in the current local workflow, and labels
scaffolded text/automatic-mask presets as mock paths. Docs now distinguish CLI
support from current local UI worker support so users do not confuse a
configurable workflow with a runnable UI job.

The working tree was not clean at phase start because `.motionjson/`,
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, and `out/demo_red_ball/` were already
untracked local/generated artifacts. At review time,
`docs/Codex Prompt Instrcution.md` was also untracked. These files were not
staged for this phase.

## Changed Files

- `src/motionjson/capabilities.py`
  - Adds explicit provider readiness, credential, model-path, GPU, runnable,
    and estimated-cost fields.
  - Adds `summary.runnableProviders` and
    `summary.localFreeRunnableProviders`.
  - Keeps `available`, `configured`, `status`, and existing provider names for
    CLI/API compatibility.
- `src/motionjson/ui/static/app.js`
  - Adds local/free, network, credential, model-path, runnable, and configured
    but not runnable chips.
  - Marks text detector and automatic-mask presets as mock/scaffolded.
  - Makes selected-provider warnings consider `runnable: false`.
  - Clarifies that the local UI worker currently starts only `mock`,
    `threshold`, and `external` jobs.
- `src/motionjson/ui/server.py`
  - Emits validation warnings when a provider is configured but not runnable.
- `README.md`, `docs/provider_capabilities.md`, `docs/discovery_providers.md`,
  `docs/local_ui.md`, `docs/troubleshooting.md`
  - Document provider readiness fields, local/free cost status, hosted
    network opt-in, and UI-vs-CLI support today.
- `scripts/build_ui_shell.mjs`
  - Extends static UI checks for the new provider chips.
- Tests:
  - `tests/test_capabilities.py`
  - `tests/test_local_ui_api.py`
  - `tests/test_track_filtering.py`
  - `tests/test_benchmark.py`
  - `tests/test_phase13_packaging_onboarding.py`

## Tests Run

- `python3 -m py_compile src/motionjson/capabilities.py src/motionjson/ui/server.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m pytest -q tests/test_capabilities.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_local_ui_api.py::test_local_ui_validation_warns_when_configured_provider_is_not_runnable tests/test_track_filtering.py tests/test_benchmark.py::test_benchmark_multi_object_external_masks_keeps_two_stable_tracks tests/test_phase13_packaging_onboarding.py::test_local_ui_exposes_first_run_diagnostics_panel tests/test_phase13_packaging_onboarding.py::test_extraction_mode_docs_include_failure_modes_and_multi_object_sample`
  - Result: 29 passed.
- `python3 -m pytest -q tests/test_capabilities.py tests/test_local_ui_api.py::test_local_ui_validation_warns_when_configured_provider_is_not_runnable`
  - Result: 17 passed after adding hosted opt-in coverage.
- `python3 -m pytest -q`
  - Result: 246 passed.
- `node --check src/motionjson/ui/static/app.js && npm test -- --runInBand`
  - Result: 19 passed.
- `npm run build`
- `npm run lint`
- `python3 -m motionjson.cli backend diagnostics --json >/tmp/motionjson-phase06-diagnostics.json && python3 -m json.tool /tmp/motionjson-phase06-diagnostics.json >/dev/null`
- `python3 -m motionjson.cli backend diagnostics --text`
- `python3 -m motionjson.cli benchmark --fixtures multi_object,whole_frame_regression --modes external --out /tmp/motionjson-phase06-benchmarks --width 64 --height 48 --frames 4`
  - Result: 2 runs, 2 passed.
- `python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-phase06-text-mock --discovery-provider text_detector --discovery-text "red ball . hand" --discovery-config '{"mock": true, "max_candidates": 2}' --mask-provider mock --max-frames 2 --min-area 1`
  - Result: extraction succeeded.
- `python3 -m motionjson.cli validate /tmp/motionjson-phase06-text-mock --object-id text_detector_red_ball`
  - Result: validated 11 MotionJSON files; skipped 9 auxiliary JSON files.
- `git diff --check`

## Screenshots And Demos Produced

No new screenshots or demo media were produced. This phase changed provider
diagnostics, UI copy/chips, docs, and CPU-safe tests.

## Review

A reviewer subagent was requested for this phase, but the subagent failed with
a usage-limit error before producing review output. Manual owner review covered
the provider capability schema, UI validation/warning paths, docs, tests, and
the final diff. No material follow-up findings were left unaddressed.

## Known Limitations

- `motion` and `motion_foreground` are CPU/no-model CLI paths, but the current
  local UI worker still starts only `mock`, `threshold`, and `external` jobs.
- `text_detector`, `class_detector`, and `sam_auto_masks` remain scaffolded
  heavy-provider surfaces unless a concrete backend is configured and wired.
  Mock mode is available for smoke tests.
- `needsGpu` is currently false for the supported local/free paths. GPU
  recommendations for future heavy providers can be added separately without
  changing the current field.
- Hosted segmentation can be credentialed while `runnable` remains false until
  explicit network opt-in or an injected client path is provided.

## Follow-Up Tasks

- Wire `motion`/`motion_foreground` through the local UI worker when the worker
  can preserve the current provider diagnostics and fallback behavior.
- Add concrete detector/Yolo/SAM automatic-mask backends behind the existing
  capability-gated scaffolds.
- Expand the provider capability report from run configs when users override
  hosted endpoint/auth environment variable names.

## 2026-05-18 Revalidation

Phase 06 was rechecked after the provider-settings phase. The provider
capability docs now include an explicit provider matrix covering local/free
status, GPU requirements, model-weight requirements, credential needs, best-use
cases, and common failure modes for local, hosted, detector, SAM2, and
OpenRouter-style providers. A docs test now asserts that the matrix remains in
the user manual. Revalidation commands passed:
`python3 -m pytest -q tests/test_phase13_packaging_onboarding.py::test_extraction_mode_docs_include_failure_modes_and_multi_object_sample tests/test_capabilities.py tests/test_benchmark.py::test_benchmark_multi_object_external_masks_keeps_two_stable_tracks tests/test_track_filtering.py`,
`python3 -m motionjson.cli backend diagnostics --json`,
`python3 -m motionjson.cli backend diagnostics --text`, and
`python3 -m motionjson.cli benchmark --fixtures multi_object,whole_frame_regression --modes external --out /tmp/motionjson-phase06-recheck-benchmarks --width 64 --height 48 --frames 4`.
