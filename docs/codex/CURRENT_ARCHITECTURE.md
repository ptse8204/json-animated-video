# Current Architecture

Use source/tests for truth. Older architecture docs were deleted or historical.

## Source Map

| Area | Paths |
| --- | --- |
| Python package/CLI | `src/motionjson/`, `src/motionjson/cli.py`, `pyproject.toml` |
| Backend API/server | `src/motionjson/backend/`, `src/motionjson/ui/server.py` |
| Local storage | `src/motionjson/backend/db.py`, default `.motionjson/backend.sqlite`, `.motionjson/storage` |
| Static UI | `src/motionjson/ui/static/index.html`, `app.js`, `config_builder.js`, `app.css`, `ui_selectors.js` |
| Extraction | `src/motionjson/config.py`, `pipeline.py`, `video.py`, `masks.py`, `tracks.py`, `track_filters.py`, `vectorize.py`, `job_artifacts.py` |
| Providers | `src/motionjson/providers/`, `src/motionjson/adapters/`, `provider_registry.py`, `provider_settings.py`, `capabilities.py` |
| Model planners | `src/motionjson/model_connectors/contracts.py` |
| Exports/schemas | `src/motionjson/exporters/`, `src/motionjson/schemas/`, `src/motionjson/rights.py` |
| JS runtime/SDK | `packages/motionjson-runtime/`, `packages/motionjson-sdk/` |

## CLI

Top-level commands: `extract`, `validate`, `correct`, `export`, `benchmark`, `backend`, `ui`.

## Current Defaults

- UI is dependency-light/static.
- Backend is local SQLite/filesystem.
- CPU/mock/no-model paths are required.
- SAM2/SAM3/detectors/hosted providers/OpenAI/OpenRouter/FFmpeg are optional or environment-dependent.
- OpenAI/OpenRouter are planners/reasoners, not segmentation providers.

## Test Map

| Area | Commands |
| --- | --- |
| Docs/context | `python3 scripts/check_codex_context_budget.py`, `python3 -m pytest -q tests/test_docs_links.py` |
| Python | `python3 -m pytest -q` |
| CLI | `python3 -m motionjson.cli --help`, `python3 -m motionjson.cli extract --help`, `python3 -m motionjson.cli backend --help`, `python3 -m motionjson.cli ui --help` |
| UI/runtime | `npm test`, `npm run lint`, `npm run build`, `npm run ui:layout` |
