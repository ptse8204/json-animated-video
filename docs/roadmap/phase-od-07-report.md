# Phase OD-07 Report: Optional SAM3 Provider Diagnostics And Mocks

## Summary

Added SAM3 provider surfaces and no-model mock discovery modes without making SAM3 part of the base install.

The backend now recognizes `sam3_concept`, `sam3_exemplar`, and `sam3_auto_masks` discovery modes. In mock mode they write normal API-first candidates, masks, review metadata, and tracks without GPU, SAM3 packages, hosted credentials, or network calls. Provider diagnostics now report local SAM3 package/model readiness and hosted SAM3 endpoint/key/network opt-in state without exposing secret values.

## Changed Files

- `README.md`
- `docs/discovery_providers.md`
- `docs/provider_capabilities.md`
- `docs/provider_pipeline.md`
- `docs/repo_status.md`
- `docs/run_config.md`
- `docs/run_local.md`
- `docs/security/api_keys.md`
- `docs/roadmap/phase-od-07-report.md`
- `pyproject.toml`
- `src/motionjson/backend/worker.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/cli.py`
- `src/motionjson/config.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_capabilities.py`
- `tests/test_cli_ui.py`
- `tests/test_discovery_providers.py`
- `tests/test_docs_links.py`
- `tests/test_phase13_packaging_onboarding.py`
- `tests/test_provider_settings.py`

## Tests Run

- `python3 -m py_compile src/motionjson/config.py src/motionjson/providers/discovery.py src/motionjson/capabilities.py src/motionjson/provider_settings.py src/motionjson/cli.py src/motionjson/backend/worker.py`
- `python3 -m pytest tests/test_discovery_providers.py tests/test_capabilities.py tests/test_provider_settings.py tests/test_cli_ui.py tests/test_docs_links.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public -q`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-od07-sam3-concept --discovery-provider sam3_concept --discovery-config '{"mock":true,"concept":"red ball","max_candidates":1}' --mask-provider mock --max-frames 2 --min-area 1`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Risk Review

The requested read-only diff-review scout could not run because the account hit the Codex usage limit. The master agent performed an owner diff review instead, covering provider diagnostics, mock discovery behavior, hosted credential redaction, optional extras, docs truthfulness, and test coverage.

## Known Limitations

- Real local SAM3 execution is not implemented in this phase. SAM3 discovery providers fail clearly unless `discovery.config.mock: true` is used or a future real adapter is wired.
- Hosted SAM3 is diagnostics/settings-only in this phase. Setup tests validate local fields and redaction but do not make network calls.
- The `sam3` optional extra prepares local ML dependencies only; users still need a compatible SAM3 package/model installed separately and `SAM3_LOCAL_MODEL` configured.

## Follow-Up Tasks

- Add the real local SAM3 adapter behind capability gates in OD-08.
- Add hosted SAM3 execution and explicit one-frame network smoke testing in OD-09.
- Keep SAM3 docs conservative until a supported runtime/package contract is verified.
