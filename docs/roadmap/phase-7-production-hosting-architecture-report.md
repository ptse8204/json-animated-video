# Phase 7 Production Hosting Architecture Report

## Summary

Implemented the prompt-pack Phase 7 hosting foundations while preserving local no-model/mock first-run behavior. The Local UI now builds an explicit deployment profile, exposes it through `/api/health`, `/api/deployment-readiness`, workspace, and commercial readiness payloads, and fails closed for hosted profiles until real hosted auth is configured.

Model planning runs now use a user-scoped SQLite store by default in `LocalUIApp`, so completed plans and events survive app restarts. The old process-local `VolatileModelRunStore` remains available for tests and narrow callers.

No Local UI layout, card, typography, visual hierarchy, or responsive behavior was changed in this phase, so no new browser screenshots were committed. Existing browser E2E coverage was run.

## Changed Files

- `src/motionjson/backend/deployment.py`
- `src/motionjson/backend/auth_context.py`
- `src/motionjson/backend/db.py`
- `src/motionjson/backend/workspace.py`
- `src/motionjson/model_connectors/__init__.py`
- `src/motionjson/model_connectors/contracts.py`
- `src/motionjson/ui/server.py`
- `tests/test_deployment_readiness.py`
- `tests/test_model_connectors.py`
- `tests/test_local_ui_api.py`
- `tests/test_local_ui_model_connectors.py`
- `docs/developer_api.md`
- `docs/local_ui.md`

The pre-existing unstaged `.gitignore` change for `codex_prompt_pack/` was left out of the phase scope.

## Tests Run

- `python3 -m pytest tests/test_deployment_readiness.py tests/test_model_connectors.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_local_ui_api.py::test_local_ui_deployment_readiness_and_hosted_mode_fail_closed tests/test_local_ui_api.py::test_local_ui_workspace_preferences_and_recent_work_are_public tests/test_local_ui_api.py::test_local_ui_commercial_readiness_surface_is_local_and_audit_friendly tests/test_local_ui_model_connectors.py -q` - 28 passed
- `python3 -m pytest tests/test_deployment_readiness.py tests/test_model_connectors.py tests/test_local_ui_api.py tests/test_local_ui_model_connectors.py -q` - 74 passed
- `python3 -m pytest tests/test_model_connectors.py -q` - 9 passed
- `python3 -m pytest` - 623 passed, 1 skipped
- `npm test` - 23 passed
- `npm run lint` - passed
- `npm run build` - passed
- `npm run test:e2e` - 8 passed
- `python3 -m motionjson.cli --help` - passed
- `python3 -m motionjson.cli extract --help` - passed
- `python3 -m motionjson.cli backend --help` - passed
- `git diff --check` - passed

## Known Limitations

- Hosted profiles are architecture placeholders only. They report blockers and return 401 on private Local UI API routes because hosted auth, external database, object storage, external queue, secrets manager, worker isolation, team mode, and billing are not implemented.
- Local UI still uses local SQLite, local files, and an in-process worker for normal local runs.
- `SQLiteModelRunStore` is local-workspace scoped. It is owner-scoped and persistent, but it is not a hosted multi-tenant model-run service.
- Queue, storage, and secrets are represented in readiness/runtime boundaries, not replaced with cloud implementations.

## Follow-Up Tasks

- Add a real hosted auth provider before enabling any hosted private routes.
- Introduce object storage and signed-content URL adapters before serving hosted assets.
- Add an external queue/worker adapter and GPU isolation model before hosted model jobs.
- Add migration/versioning strategy for any future model-run schema changes.
- Add team/workspace membership and billing controls before marking hosted readiness true.

## Scout Notes

- `plan-risk-scout` was used before implementation. The scout called out strict hosted fail-closed behavior, owner-scoped persistent model runs, redaction coverage for model-run paths, explicit hosted profile selection, and the prompt-pack Phase 7 versus active roadmap phase mismatch.
- `diff-review-scout` reviewed the final diff and found a missing SQLite model-run trim validation. A focused test was added for owner-scoped trimming and cascaded event cleanup, then `tests/test_model_connectors.py` and the full Python suite were rerun successfully.
