---
historical: true
default_context: false
---

# Phase UI-MODEL-03 Report

## Summary

Wired the model planning provider contract to the existing Local UI provider
settings system. The default `fake-local-planner` remains local, runnable, and
no-network. A new `openrouter-planner` provider exposes OpenRouter readiness
through the model-provider routes while preserving server-side credential
storage, redacted responses, environment precedence, hosted cost/privacy
opt-in, and no-network default behavior.

`openrouter-planner` is intentionally settings-only in this phase: it can report
configuration, run the existing no-network settings test, and return a blocked
hosted-cost estimate, but model runs reject it until the hosted planning
transport is implemented.

## Changed Files

- `src/motionjson/model_connectors/__init__.py`
- `src/motionjson/model_connectors/contracts.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/ui/server.py`
- `tests/test_model_connectors.py`
- `tests/test_local_ui_model_connectors.py`
- `tests/test_provider_settings.py`
- `docs/local_ui.md`
- `docs/roadmap/phase-ui-model-03-report.md`

## Tests Run

- `python3 -m pytest -q tests/test_model_connectors.py tests/test_local_ui_model_connectors.py tests/test_provider_settings.py`
- `python3 -m pytest -q tests -k "model or provider or ui"`
- `python3 -m pytest -q`
- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Review Notes

- The requested read-only diff-review scout could not complete because the
  Codex subagent usage limit was reached.
- The master agent performed a manual review of the final diff for secret
  leakage, hosted-call gating, accidental network paths, provider settings
  precedence, and non-runnable hosted planning behavior.

## Known Limitations

- Hosted model planning is not implemented yet. `openrouter-planner` stays
  non-runnable even when OpenRouter settings and hosted opt-in are configured.
- The estimate route does not call hosted billing or token-estimation APIs; it
  reports `unknown_provider_cost` and a blocked reason.
- Model runs remain process-local and volatile from UI-MODEL-02.

## Follow-Up Tasks

- Add the OpenAI/OpenAI-compatible planning connector with mocked transport and
  no-network default behavior in UI-MODEL-04.
- Add UI setup and confirmation flows for model provider readiness in
  UI-MODEL-05 and UI-MODEL-06.
- Persist model run history only if a later phase requires recovery across UI
  restarts.
