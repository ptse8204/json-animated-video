# Phase 05 Report: First-Run Diagnostics

Date: 2026-05-16

## Summary

Phase 05 improved first-run diagnostics without changing the existing JSON
diagnostics contract. `motionjson backend diagnostics` still emits JSON by
default, and `--json` remains supported. A new `--text` option prints a compact
human-readable summary for normal users.

The local UI First Run checklist now consumes capability summary fields from
the backend, shows whether no-model smoke checks are ready, lists optional
providers as non-blocking setup, and gives the next action for a CPU/mock run.
Provider warnings returned from UI config validation now include severity and a
concrete action.

The working tree was not clean at phase start because `.motionjson/`,
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, and `out/demo_red_ball/` were already
untracked local/generated artifacts. They were not staged for this phase.

## Changed Files

- `src/motionjson/capabilities.py`
  - Adds first-run summary fields:
    - `readyNoModelProviders`;
    - `canRunNoModelSmoke`;
    - `firstRun`;
    - `unavailableRequiredSetup`.
  - Adds `format_capability_report()` for human-readable diagnostics.
- `src/motionjson/backend/cli.py`
  - Adds `backend diagnostics --text`.
  - Keeps JSON as the default output and lets `--json` win when both output
    flags are provided.
- `src/motionjson/ui/static/app.js`
  - Updates the First Run checklist to show ready no-model providers, optional
    setup, FFmpeg status, and next action.
- `src/motionjson/ui/server.py`
  - Adds `severity` and `action` fields to local UI provider warnings.
- `src/motionjson/providers/sam2.py`
  - Adds diagnostics command guidance to local SAM2 setup failures.
- `README.md`, `docs/first_run.md`, `docs/local_ui.md`,
  `docs/provider_capabilities.md`, `docs/troubleshooting.md`
  - Document the new text diagnostics path and UI behavior.
- Tests:
  - `tests/test_capabilities.py`
  - `tests/test_cli_ui.py`
  - `tests/test_discovery_providers.py`
  - `tests/test_local_ui_api.py`
  - `tests/test_phase13_packaging_onboarding.py`

## Tests Run

- `python3 -m py_compile src/motionjson/capabilities.py src/motionjson/backend/cli.py src/motionjson/ui/server.py src/motionjson/providers/sam2.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m motionjson.cli backend diagnostics --text`
- `python3 -m motionjson.cli backend diagnostics --json >/tmp/motionjson-phase05-diagnostics.json && python3 -m json.tool /tmp/motionjson-phase05-diagnostics.json >/dev/null`
- `python3 -m motionjson.cli backend diagnostics --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-phase05-sam2-fail --mask-provider sam2-local --prompt-point 10,10 --max-frames 1`
  - Expected failure; verified the error points to `backend diagnostics --text`.
- `python3 -m pytest -q tests/test_capabilities.py tests/test_cli_ui.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_local_ui_api.py::test_local_ui_capabilities_preserve_provider_failure_details tests/test_local_ui_api.py::test_local_ui_run_config_validation_uses_existing_config_code_and_warns tests/test_discovery_providers.py::test_mock_text_detector_discovery_cli_smoke_uses_detector_candidates tests/test_sam2_providers.py tests/test_phase13_packaging_onboarding.py::test_local_ui_exposes_first_run_diagnostics_panel`
  - Result: 33 passed.
- `python3 -m pytest -q`
  - Result: 241 passed.
- `npm run build`
- `npm test`
  - Result: 19 passed.
- `npm run lint`
- `git diff --check`
- Reviewer verification:
  - No material findings.
  - `python3 -m pytest tests/test_capabilities.py tests/test_cli_ui.py tests/test_local_ui_api.py tests/test_discovery_providers.py -q`
    - Result: 53 passed.
  - `python3 -m motionjson.cli backend diagnostics --text`
  - `python3 -m motionjson.cli backend diagnostics --json`

## Screenshots And Demos Produced

No new screenshots or demo assets were produced in Phase 05. The UI changes are
covered by static JS checks and API/unit tests. Existing Phase 03 screenshots
remain current enough for README use.

## Known Limitations

- The text diagnostics summary is intentionally compact; users still need
  `--json` for the full provider matrix.
- The UI First Run checklist reports capability status but does not install
  optional SAM2, detector, hosted, or FFmpeg dependencies.
- The mock text-detector CLI smoke uses deterministic mock discovery; it does
  not claim a real open-vocabulary detector is installed.

## Follow-Up Tasks

- Phase 06 should expand provider documentation with explicit local/free, GPU,
  model-weight, credential, estimated cost, and failure-mode fields.
- Future UI polish can add a dedicated one-click seeded demo flow; Phase 05
  keeps the existing project/video/job workflow and makes the next action
  clearer.
