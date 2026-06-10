---
historical: true
default_context: false
---

# Phase UI-MODEL-02 Report

## Summary

Added the server-side model planning connector contract for the Local UI without
adding hosted calls or browser-side credentials. The implementation includes a
typed `motionjson.model_connectors` package, a deterministic fake local
planner, volatile thread-safe model run storage, route handlers for provider
listing/readiness/test/estimate/start/poll/events/cancel, and a job attachment
route that records a redacted `model_plan_attached` job event.

## Changed Files

- `src/motionjson/model_connectors/__init__.py`
- `src/motionjson/model_connectors/contracts.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_model_connectors.py`
- `tests/test_local_ui_model_connectors.py`
- `docs/local_ui.md`
- `docs/roadmap/phase-ui-model-02-report.md`

## Tests Run

- `python3 -m pytest -q tests/test_model_connectors.py tests/test_local_ui_model_connectors.py`
- `python3 -m pytest -q tests/test_model_connectors.py tests/test_local_ui_model_connectors.py tests/test_local_ui_api.py tests/test_provider_settings.py`
- `python3 -m pytest -q tests -k "model or provider or ui"`
- `python3 -m pytest -q`
- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known Limitations

- Only `fake-local-planner` is implemented. It is deterministic, local, and
  no-network.
- Model runs are process-local and volatile. Persisted extraction jobs only get
  a redacted attachment event in this phase.
- `POST /api/jobs/{jobId}/model-plan` does not enqueue extraction. Manual
  confirmation and extraction enqueueing remain later phase work.
- Provider settings are not wired into connector readiness yet; that belongs to
  UI-MODEL-03.

## Follow-Up Tasks

- Wire provider settings and hosted-call opt-in to connector readiness in
  UI-MODEL-03.
- Add the OpenAI planning connector with mocked transport and no-network default
  behavior in UI-MODEL-04.
- Connect plan confirmation to extraction enqueueing in UI-MODEL-06.
