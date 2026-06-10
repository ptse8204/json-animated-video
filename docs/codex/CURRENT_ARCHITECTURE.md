# Current Architecture

This is the compact source-of-truth map for current implementation. Older architecture docs can be aspirational or historical; inspect source before relying on them.

## Python Package And CLI

- Package: `src/motionjson/`
- Package metadata: `pyproject.toml`
- Console script: `motionjson = motionjson.cli:main`
- CLI entrypoint: `src/motionjson/cli.py`

Top-level CLI commands:

- `extract`
- `validate`
- `correct`
- `export`
- `benchmark`
- `backend`
- `ui`

Backend subcommands are registered in `src/motionjson/backend/cli.py`.

## Backend And Local UI Server

- Local UI launcher: `python3 -m motionjson.cli ui`
- UI server: `src/motionjson/ui/server.py`
- Backend API: `src/motionjson/backend/api.py`
- Workspace DB schema: `src/motionjson/backend/db.py`
- Projects/assets/jobs: `src/motionjson/backend/projects.py`, `src/motionjson/backend/assets.py`, `src/motionjson/backend/jobs.py`
- Queue/worker/lifecycle: `src/motionjson/backend/queue.py`, `src/motionjson/backend/worker.py`, `src/motionjson/backend/job_lifecycle.py`, `src/motionjson/backend/stale_jobs.py`
- Default local DB: `.motionjson/backend.sqlite`
- Default local storage root: `.motionjson/storage`

The backend uses SQLite and local filesystem storage for current local workflows.

## Static UI

- HTML shell: `src/motionjson/ui/static/index.html`
- UI logic: `src/motionjson/ui/static/app.js`
- Config builder: `src/motionjson/ui/static/config_builder.js`
- CSS: `src/motionjson/ui/static/app.css`
- Selector constants: `src/motionjson/ui/static/ui_selectors.js`

The current UI is dependency-light/static. Do not assume React/Vite exists unless a task explicitly changes architecture.

## Extraction Pipeline

- Run config: `src/motionjson/config.py`
- Main pipeline: `src/motionjson/pipeline.py`
- Video IO: `src/motionjson/video.py`
- Masks: `src/motionjson/masks.py`
- Tracks: `src/motionjson/tracks.py`
- Track filtering/fallback reasons: `src/motionjson/track_filters.py`
- Vectorization: `src/motionjson/vectorize.py`
- Candidate review: `src/motionjson/candidate_review.py`
- Corrections: `src/motionjson/corrections.py`
- Job artifacts: `src/motionjson/job_artifacts.py`

## Providers

- Provider interfaces: `src/motionjson/providers/base.py`
- Registry/capabilities: `src/motionjson/provider_registry.py`, `src/motionjson/capabilities.py`
- Provider settings/redaction: `src/motionjson/provider_settings.py`
- Discovery providers: `src/motionjson/providers/discovery.py`
- Segmentation adapters: `src/motionjson/providers/segmentation.py`
- Mocks/no-model providers: `src/motionjson/providers/mocks.py`
- SAM2 providers: `src/motionjson/providers/sam2.py`, `src/motionjson/adapters/sam2_provider.py`, `src/motionjson/adapters/sam2_replicate.py`, `src/motionjson/adapters/sam2_runpod.py`
- SAM3 providers/workers: `src/motionjson/providers/sam3.py`, `src/motionjson/backend/sam3_discovery_worker.py`, `src/motionjson/backend/sam3_discovery_subprocess.py`, `src/motionjson/backend/sam3_smoke_worker.py`, `src/motionjson/backend/sam3_smoke_subprocess.py`
- Hosted SAM provider helpers: `src/motionjson/providers/hosted_sam.py`
- OpenRouter reasoning provider: `src/motionjson/providers/openrouter.py`
- External masks: `src/motionjson/adapters/external_masks.py`

## Model Connectors

- Connector contracts and fake/OpenAI planning connectors: `src/motionjson/model_connectors/contracts.py`
- UI/API integration tests: `tests/test_model_connectors.py`, `tests/test_local_ui_model_connectors.py`

Model connectors are planning/reasoning surfaces. They do not own segmentation or tracking.

## Export And Runtime

- Exporters: `src/motionjson/exporters/`
- Schemas: `src/motionjson/schemas/`
- Rights metadata: `src/motionjson/rights.py`, `src/motionjson/backend/rights.py`
- JS runtime package: `packages/motionjson-runtime/`
- JS SDK package: `packages/motionjson-sdk/`
- Runtime tests: `packages/motionjson-runtime/test/runtime.test.mjs`
- SDK tests: `packages/motionjson-sdk/test/sdk.test.mjs`

## Implemented Vs Optional

Implemented and CPU/mock testable:

- CLI extraction, validation, correction, export, benchmark, backend, UI launch.
- SQLite-backed local backend and filesystem artifacts.
- Static Local UI.
- Mock/no-model providers and deterministic smoke paths.
- Provider diagnostics and settings redaction.
- Review/correction/export state and local artifact workflows.
- JS runtime/SDK tests.

Optional or environment-dependent:

- Local SAM2/SAM3.
- CUDA acceleration.
- Detector packages and weights.
- Hosted SAM-style providers.
- OpenAI/OpenRouter planning.
- FFmpeg final video rendering.
- Browser screenshot tooling availability.

## Key Validation Commands

```bash
python3 -m pytest -q
python3 -m pytest -q tests/test_docs_links.py
python3 -m motionjson.cli --help
python3 -m motionjson.cli extract --help
python3 -m motionjson.cli backend --help
python3 -m motionjson.cli ui --help
npm test
npm run lint
npm run build
git diff --check
```
