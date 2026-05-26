# Phase UI First Run Validation Report

## Summary

- Updated the public docs, first-run guide, Local UI docs, SAM2/SAM3 provider docs, system requirements, troubleshooting, and Colab notebook copy so UI-owned Model setup is the primary path.
- Clarified the SAM3 split everywhere relevant: `sam3TrackerModel=facebook/sam3` or a local Hugging Face model directory is for Scene Sweep, while `sam3ModelPath`/`SAM3_LOCAL_MODEL=/.../sam3.pt` is Advanced official-package concept/exemplar configuration only.
- Documented `SAM2 HF automatic masks` as the fallback scene-sweep provider using `facebook/sam2.1-hiera-large`, independent from official SAM2 prompt tracking.
- Updated the Colab provider-connect notebook to install only `.[ui]`, launch the same main Local UI, and keep SAM package/checkpoint helpers under Advanced fallback/debugging.
- Removed remaining normal UI copy that exposed `SAM3_LOCAL_MODEL` and the old `Model Connections` label in the main setup path.

## Changed Files

- `README.md`
- `docs/first_run.md`
- `docs/local_ui.md`
- `docs/sam3_local.md`
- `docs/sam2_segmentation.md`
- `docs/system_requirements.md`
- `docs/provider_capabilities.md`
- `docs/discovery_providers.md`
- `docs/run_config.md`
- `docs/run_local.md`
- `docs/troubleshooting.md`
- `docs/index.md`
- `docs/repo_status.md`
- `docs/design/local-ui-product-principles.md`
- `notebooks/README.md`
- `notebooks/colab_ui_provider_connect_demo.ipynb`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_colab_notebooks.py`
- `tests/test_phase10_free_hosted_demos.py`
- `docs/design/screenshots/ui-first-run-final/`

## Tests Run

- `python3 -m json.tool notebooks/colab_ui_provider_connect_demo.ipynb >/dev/null`
- `python3 -m pytest -q tests/test_colab_notebooks.py tests/test_phase10_free_hosted_demos.py::test_colab_ui_provider_connect_notebook_uses_private_colab_proxy_and_vendor_profiles tests/test_docs_links.py`
- `python3 -m pytest`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `npm test`
- `npm run lint`
- `npm run build`
- `node --check src/motionjson/ui/static/app.js`
- `node --check src/motionjson/ui/static/config_builder.js`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-first-run-final --state workflow-goal,workflow-video,workflow-provider,model-setup-sam3-local,prepare-sam3-trace-all,workflow-run,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `git diff --check`

## Visual Evidence

- Final screenshots: `docs/design/screenshots/ui-first-run-final/`
- Captured viewports: `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and `1920x1080`.
- Captured states: goal, video, normal model setup, SAM3 Scene Sweep setup, SAM3 trace-all prepare/run configuration, run monitor, and failed-run recovery.

## Known Limitations

- The layout screenshot command still prints a non-fatal Python `resource_tracker` semaphore warning during mock job shutdown.
- The Colab notebook is structurally/source validated in this phase; it was not executed end to end inside a live Colab runtime.
- Real SAM3/SAM2 HF runtime smoke tests remain capability-gated and were not run without the optional model runtimes and model access.

## Follow-Up Tasks

- Keep future docs and UI copy using `Model setup` for the normal path and reserve environment variables, local paths, checkpoint files, custom endpoints, and manual commands for Advanced.
- Add byte-level Hugging Face model-cache progress if a future dependency provides a stable progress callback.
- Add real-environment SAM3 Scene Sweep and SAM2 HF smoke notes once a supported GPU/runtime fixture is available.
