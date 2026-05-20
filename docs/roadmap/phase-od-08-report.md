# Phase OD-08 Report: Optional Local SAM3 Adapter

## Summary

Added an optional local SAM3 discovery adapter behind capability gates.

The adapter lazy-imports the official SAM3 image processor and video predictor paths only when a real non-mock SAM3 run is requested. It supports injected fake processors/predictors for CI, concept discovery, exemplar/box discovery, broad semantic auto proposals, one-frame smoke testing, video-session mask sequences, and conversion into MotionJSON's shared API-first candidate/review artifact shape.

Diagnostics now gate real SAM3 local readiness on the `sam3` package, Python 3.12+, torch with CUDA available, and `SAM3_LOCAL_MODEL`. Mock SAM3 discovery remains no-model and runnable for tests and local UI smoke checks.

## Changed Files

- `README.md`
- `docs/discovery_providers.md`
- `docs/index.md`
- `docs/provider_capabilities.md`
- `docs/provider_pipeline.md`
- `docs/repo_status.md`
- `docs/run_config.md`
- `docs/run_local.md`
- `docs/sam3_local.md`
- `docs/roadmap/phase-od-08-report.md`
- `pyproject.toml`
- `src/motionjson/backend/worker.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/providers/__init__.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/sam3.py`
- `tests/test_backend_jobs_worker.py`
- `tests/test_capabilities.py`
- `tests/test_discovery_providers.py`
- `tests/test_docs_links.py`
- `tests/test_sam3_providers.py`

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/discovery.py src/motionjson/capabilities.py src/motionjson/provider_settings.py src/motionjson/backend/worker.py src/motionjson/providers/__init__.py tests/test_sam3_providers.py tests/test_capabilities.py tests/test_backend_jobs_worker.py tests/test_discovery_providers.py`
- `python3 -m pytest tests/test_sam3_providers.py tests/test_discovery_providers.py tests/test_capabilities.py tests/test_backend_jobs_worker.py tests/test_provider_settings.py tests/test_cli_ui.py tests/test_docs_links.py -q`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-od08-sam3-mock --discovery-provider sam3_concept --discovery-config '{"mock":true,"concept":"red ball","max_candidates":1}' --mask-provider mock --max-frames 2 --min-area 1`
- Expected failure check: non-mock `sam3_concept` without `SAM3_LOCAL_MODEL` exits with `SAM3 local adapter requires SAM3_LOCAL_MODEL or discovery.config.sam3ModelPath.`
- `python3 -m motionjson.cli backend diagnostics --json`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Risk Review

The requested plan-risk scout could not run because the account hit the Codex usage limit. The master agent performed the risk review in-thread, focusing on optional dependency safety, lazy imports, SAM3 runtime honesty, no-model test paths, API-owned candidates, and docs truthfulness.

The adapter follows the official `facebookresearch/sam3` documented entry points where possible: `build_sam3_image_model`, `Sam3Processor`, and `build_sam3_video_predictor`. The docs link to the official repository as the source of truth for runtime setup.

## Known Limitations

- Real SAM3 was not executed in this environment; CI uses injected fake SAM3 processors and predictors.
- The adapter normalizes common SAM3 output shapes, but exact real-world package responses may need additional normalization once a supported SAM3 environment is available.
- Local SAM3 is treated as CUDA-gated for real execution. CPU/mock paths remain available without SAM3.
- Hosted SAM3 execution remains OD-09.

## Follow-Up Tasks

- Run the optional real SAM3 smoke test with `MOTIONJSON_RUN_REAL_SAM3_TESTS=1` and `SAM3_LOCAL_MODEL` in a compatible SAM3 environment.
- Add hosted SAM3 execution with explicit cost/privacy opt-in in OD-09.
- Expand UI affordances for concept/exemplar inputs after hosted and local SAM3 paths stabilize.
