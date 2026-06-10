---
historical: true
default_context: false
---

# Phase Provider UI 02 Report

## Summary

Implemented the real SAM Model Connections experience for the Local UI. The normal workflow now leads with SAM setup instead of planner setup, recommends local or hosted SAM providers by user goal, and keeps mock/no-model execution behind explicit debug mode. Users can link Roboflow SAM3, Replicate SAM2 video, Fal SAM3 image, custom SAM-compatible endpoints, or in-process local SAM2/SAM3 settings from the UI.

The backend provider settings API now persists local SAM fields, returns redacted readiness metadata, exposes a no-network diagnose endpoint, and supports bounded local SAM smoke tests that require explicit heavy-local consent. Hosted smoke tests remain opt-in with network, hosted, and cost/privacy acknowledgement flags.

The Colab provider-connect notebook was expanded into a real hosted/local SAM setup notebook. It checks the GPU runtime, loads hosted keys and Hugging Face credentials from Colab userdata or prompts, includes optional local SAM2/SAM3 setup cells, launches `motionjson ui --no-open --host 127.0.0.1`, and opens the UI through Colab's built-in port proxy only.

## Changed Files

- `.devcontainer/devcontainer.json`: default UI command now uses the normal real-provider path.
- `src/motionjson/provider_settings.py`: local SAM2/SAM3 settings, setup guide metadata, profile readiness, redacted local paths, no-network diagnostics, hosted opt-in enforcement, and local smoke tests.
- `src/motionjson/ui/server.py`: diagnose route, local smoke dispatch, and real-provider defaults for run config API responses.
- `src/motionjson/cli.py`: added `motionjson ui --debug-mock`; kept hidden deprecated `--mock` alias with warning.
- `src/motionjson/config.py`: allows SAM2/SAM3 real-provider configs without requiring manual prompts unless manual prompt mode is selected.
- `src/motionjson/capabilities.py`: reads saved local SAM settings and reports real setup gaps in diagnostics.
- `src/motionjson/ui/static/index.html`, `app.css`, `app.js`, `config_builder.js`: Model Connections cards, hosted linking flow, local SAM setup fields, diagnose/smoke controls, debug-only mock display, and real-provider run config generation.
- `notebooks/colab_ui_provider_connect_demo.ipynb`: hosted/local SAM Colab UI setup notebook without mock launch.
- `notebooks/colab_ui_local_demo.ipynb`: debug mock flag renamed to `--debug-mock`.
- `README.md`, `notebooks/README.md`, `docs/local_ui.md`, `docs/run_local.md`, `docs/run_free_instances.md`, `docs/first_run.md`, `docs/discovery_providers.md`, `docs/provider_capabilities.md`, `docs/sam2_segmentation.md`, `docs/sam3_local.md`, `docs/security/api_keys.md`, `docs/troubleshooting.md`, `docs/design/local-ui-product-principles.md`: real SAM setup, provider linking, Colab badges, local SAM guidance, and contributor-only debug mock documentation.
- `scripts/build_ui_shell.mjs`, `scripts/check_local_ui_layout.mjs`, `scripts/first_run_local.sh`, `scripts/first_run_local.ps1`, `scripts/run_local_ui_mock.sh`, `scripts/test_ui_config_builder.mjs`: updated smoke/build expectations and debug mock launch paths.
- `tests/test_provider_settings.py`, `tests/test_cli_ui.py`, `tests/test_local_ui_api.py`, `tests/test_phase03b_provider_settings_ui.py`, `tests/test_phase8_ui_config_builder.py`, `tests/test_phase10_free_hosted_demos.py`, `tests/test_phase13_packaging_onboarding.py`, `tests/test_capabilities.py`: coverage for local settings, diagnostics, CLI alias behavior, UI strings, real run configs, docs/notebook constraints, and no key leakage.
- `docs/design/screenshots/phase-provider-ui-02-before/` and `docs/design/screenshots/phase-provider-ui-02/`: before/after browser evidence.

## Tests Run

- `python3 -m py_compile src/motionjson/config.py src/motionjson/provider_settings.py src/motionjson/ui/server.py src/motionjson/capabilities.py src/motionjson/cli.py`
- `node --check src/motionjson/ui/static/app.js && node --check src/motionjson/ui/static/config_builder.js`
- `python3 -m pytest tests/test_provider_settings.py tests/test_cli_ui.py tests/test_phase03b_provider_settings_ui.py tests/test_phase8_ui_config_builder.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public -q`
- `python3 -m pytest tests/test_phase10_free_hosted_demos.py tests/test_docs_links.py tests/test_capabilities.py tests/test_phase13_packaging_onboarding.py tests/test_local_ui_api.py::test_local_ui_capabilities_preserve_provider_failure_details -q`
- `python3 -m pytest tests/test_provider_settings.py tests/test_sam2_providers.py tests/test_sam3_providers.py -q`
- `python3 -m pytest tests/test_provider_settings.py tests/test_sam2_providers.py tests/test_sam3_providers.py tests/test_phase10_free_hosted_demos.py tests/test_docs_links.py tests/test_phase03b_provider_settings_ui.py tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py tests/test_cli_ui.py -q`
- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-provider-ui-02 --state workflow-provider,provider-settings,model-setup,extraction-wizard --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `python3 -m json.tool notebooks/colab_ui_provider_connect_demo.ipynb`
- `python3 -m json.tool notebooks/colab_ui_local_demo.ipynb`
- Verified all checked-in notebooks have empty outputs.
- Verified notebooks and docs contain no public tunnel helper markers.
- `git diff --check`
- `bash -n scripts/first_run_local.sh scripts/run_local_ui_mock.sh`

The full targeted pytest command completed with `111 passed, 1 skipped`. `npm test` completed with `21` Node tests passing. The layout pass completed with status `ok` for the requested viewport/state matrix. Python emitted a shutdown `resource_tracker` semaphore warning after the layout command had completed; the command exited successfully.

`pwsh` is not installed in this environment, so PowerShell syntax validation for `scripts/first_run_local.ps1` could not be run.

## Browser Evidence

Before screenshots were captured in `docs/design/screenshots/phase-provider-ui-02-before/` with 25 PNG files.

After screenshots were captured in `docs/design/screenshots/phase-provider-ui-02/` with 25 PNG files. The after set includes workflow provider setup, provider settings, model setup, and extraction wizard states across `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.

The Model Connections after screenshots show SAM2 local, Replicate SAM2 video, SAM3 local, Roboflow SAM3 concept, and Fal SAM3 image as the primary setup cards. Mock provider rows only appear in the layout smoke run because that runner starts the UI with explicit `--debug-mock`.

## Known Limitations

- Real hosted vendor calls were not made during validation because they require user credentials, network consent, and possible provider costs. Unit tests continue to use fake clients/transports.
- Local SAM smoke tests require configured model paths and `allowHeavyLocal: true`; missing checkpoints, configs, packages, CUDA, or Hugging Face setup are reported through diagnostics instead of falling back to mock.
- SAM3 local setup depends on upstream package/model availability and access requirements. The UI and notebook surface setup commands and token status, but do not download gated weights automatically.
- Fal SAM3 remains a frame-by-frame image fallback, not a native video tracker.

## Follow-Up Tasks

- Add optional live integration tests gated by environment flags for Roboflow, Replicate, Fal, and local SAM model files.
- Add provider-specific cost estimate copy once stable vendor pricing metadata is available through public APIs.
- Add a first-run checklist that detects saved local paths and can preselect the best recommended provider per workflow without opening the advanced settings panel.
