# Phase UI-MODEL-04 Report

## Summary

Added a server-side `openai-planner` connector for the Local UI model planning
contract. The connector uses the OpenAI Responses API request shape with
structured JSON output, accepts injected transports for tests, and remains
hosted-call gated by default.

OpenAI provider settings now support `OPENAI_API_KEY`, optional
`OPENAI_BASE_URL`, `OPENAI_DEFAULT_MODEL`, saved Local UI credentials, redacted
public responses, environment precedence, and hosted-call opt-in. Model runs
require both provider opt-in and per-request `allowNetwork: true` plus
`acknowledgeCostPrivacy: true` before any transport is called.

Model output is treated as a proposed plan rather than extraction truth:
MotionJSON sanitizes hosted prompt context, maps the proposal back to explicit
CV providers, generates the `ExtractionRunConfig` locally, validates it, and
sets `requiresUserConfirmation: true`.

## Changed Files

- `README.md`
- `docs/ai_provider_architecture.md`
- `docs/local_ui.md`
- `docs/security/api_keys.md`
- `docs/roadmap/phase-ui-model-04-report.md`
- `src/motionjson/model_connectors/__init__.py`
- `src/motionjson/model_connectors/contracts.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/server.py`
- `tests/test_model_connectors.py`
- `tests/test_local_ui_model_connectors.py`
- `tests/test_provider_settings.py`

## Tests Run

- `python3 -m pytest -q tests/test_model_connectors.py tests/test_local_ui_model_connectors.py tests/test_provider_settings.py`
- `python3 -m pytest -q tests/test_model_connectors.py tests/test_local_ui_model_connectors.py tests/test_provider_settings.py tests/test_openrouter_provider.py`
- `python3 -m pytest -q tests -k "model or provider or ui or openai"`
- `python3 -m pytest -q`
- `npm run build`
- `npm test`
- `npm run lint`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-04`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Screenshot/Layout Evidence

- `docs/design/screenshots/ui-model-04/` contains 61 browser-rendered screenshots
  across the required layout viewports and Local UI states.
- The layout run exited `ok` with the known Python resource-tracker semaphore
  warning seen in earlier UI phases. No horizontal overflow, overlap, clipped
  control text, or too-narrow visible provider cards were reported.
- The UI layout/CSS was not changed in this phase; the screenshot pass verifies
  that the additional OpenAI provider settings surface still fits the existing
  provider panel layout.

## Review Notes

- OpenAI docs were checked from official OpenAI documentation for current
  Responses API structured output and model guidance.
- The requested plan-risk and diff-review scouts could not be used because the
  Codex subagent usage limit was reached during UI-MODEL-03. The master agent
  performed manual risk review for hosted-call gating, secret redaction, and
  network defaults.

## Known Limitations

- The connector sends text intent and redacted project context only. It does
  not inspect video frames or generate masks.
- Cost estimates remain `unknown_provider_cost`; no hosted billing or token
  estimation API is called.
- Model runs are still process-local and volatile from UI-MODEL-02.
- The UI setup wizard for connecting providers belongs to UI-MODEL-05.

## Follow-Up Tasks

- Add the nontechnical model setup UI in UI-MODEL-05.
- Route confirmed model plans into extraction jobs in UI-MODEL-06.
- Add persisted model-run history only if later phases need restart recovery.
