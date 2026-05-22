# Phase Provider UI 01 Report

## Summary

Implemented hosted SAM provider profile support in the Local UI and backend runtime path. The provider settings flow now exposes Replicate SAM2 video, Roboflow SAM3 concept segmentation, Fal SAM3 image, and custom SAM2/SAM3-compatible profiles. Saved server-side settings can be used by the local worker for explicit hosted runs while API responses, generated run configs, screenshots, notebooks, and docs continue to avoid raw keys.

Added `notebooks/colab_ui_provider_connect_demo.ipynb`, which installs `.[ui,hosted-segmentation,hosted-sam3,hosted-sam-vendors]`, reads `ROBOFLOW_API_KEY`, `REPLICATE_API_TOKEN`, and `FAL_KEY` from Colab userdata or `getpass`, launches `motionjson ui --no-open --mock --host 127.0.0.1`, and opens `/ui/` through Colab's built-in port proxy only.

Provider research anchors used for the runtime shapes:

- Roboflow SAM3 docs: `https://docs.roboflow.com/deploy/supported-models/sam3`
- Replicate SAM2 video API/readme: `https://replicate.com/meta/sam-2-video/api`
- Replicate input file docs: `https://replicate.com/docs/topics/predictions/input-files`
- Fal SAM3 image API: `https://fal.ai/models/fal-ai/sam-3/image/api`
- Fal Python client docs: `https://docs.fal.ai/reference/client-libraries/python/index`

## Changed Files

- `src/motionjson/provider_settings.py`: hosted profiles, `hostedProfileId`, redacted effective profile responses, smoke tests for `sam2-hosted` and `sam3-hosted`.
- `src/motionjson/providers/hosted_sam.py`: Replicate SAM2 video, Roboflow SAM3 concept, and Fal SAM3 image adapters with fake-client testability.
- `src/motionjson/providers/sam2.py`, `src/motionjson/providers/discovery.py`, `src/motionjson/backend/worker.py`: runtime wiring from saved Local UI settings into hosted extraction/discovery without serializing secrets into run configs.
- `src/motionjson/capabilities.py`: hosted profile diagnostics, missing SDK checks, and `hosted-sam-vendors` optional-extra reporting.
- `src/motionjson/ui/static/*`: provider profile selectors, hosted smoke buttons for SAM2/SAM3, text-discovery Hosted SAM3 selection, and generated run-config profile fields.
- `pyproject.toml`: added `hosted-sam-vendors`.
- `notebooks/colab_ui_provider_connect_demo.ipynb`, `README.md`, `notebooks/README.md`, `docs/run_free_instances.md`: Colab provider-connect notebook and Colab badge links for every checked-in notebook.
- `docs/local_ui.md`, `docs/provider_capabilities.md`, `docs/run_config.md`, `docs/security/api_keys.md`, `docs/sam2_segmentation.md`, `docs/sam3_hosted.md`: user-facing hosted profile/setup docs.
- `tests/*` and `scripts/test_ui_config_builder.mjs`: fake transport/client coverage, UI config coverage, redaction checks, notebook/docs checks.
- `docs/design/screenshots/phase-provider-ui-01-before/` and `docs/design/screenshots/phase-provider-ui-01/`: before/after browser evidence.

## Tests Run

- `python3 -m py_compile src/motionjson/provider_settings.py src/motionjson/providers/hosted_sam.py src/motionjson/backend/worker.py src/motionjson/providers/discovery.py src/motionjson/providers/sam2.py src/motionjson/capabilities.py`
- `python3 -m pytest tests/test_provider_settings.py tests/test_sam2_providers.py tests/test_sam3_providers.py tests/test_phase10_free_hosted_demos.py tests/test_docs_links.py tests/test_phase03b_provider_settings_ui.py tests/test_local_ui_api.py -q`
- `python3 -m pytest tests/test_phase8_ui_config_builder.py -q`
- `python3 -m json.tool notebooks/colab_ui_provider_connect_demo.ipynb`
- Verified all checked-in notebooks have empty outputs.
- Verified notebooks/docs contain no public tunnel helper markers.
- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-provider-ui-01`

The layout pass completed with status `ok` for `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`. Python emitted a shutdown `resource_tracker` warning for one leaked semaphore after the layout tool had completed; the command exited successfully.

## Browser Evidence

Before screenshots were captured in `docs/design/screenshots/phase-provider-ui-01-before/`. The initial layout process stalled after writing screenshots, so it was stopped before implementation.

After screenshots were captured in `docs/design/screenshots/phase-provider-ui-01/`. The after run completed successfully and includes provider settings, guided mode/provider setup, model setup, review, correction, and export states across the required viewports.

## Known Limitations

- Real hosted provider calls were not made during validation; unit tests use fake transports/clients to avoid costs and secrets.
- Replicate SAM2 video extraction depends on the vendor SDK and actual provider response shape for `black_white_masks`; missing SDKs fail as diagnostics.
- Roboflow and Fal hosted SAM3 paths operate on sampled frames and route masks through review/filter/linking. They do not provide full native video tracking beyond the sampled-frame mask sequence path in this phase.
- The Colab notebook launches the UI in `--mock` mode first. Users must explicitly save provider settings and accept hosted cost/privacy prompts before real hosted calls.

## Follow-Up Tasks

- Add provider-specific integration smoke tests behind opt-in environment flags for users who want to validate real vendor accounts.
- Add richer UI affordances for per-run hosted cost estimates when provider pricing metadata is available.
- Expand profile-specific docs with screenshots of the provider settings row after the first public release candidate settles.
