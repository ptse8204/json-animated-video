# Phase real-colab-sam-local-model-verification report

## Summary

- Used the existing Chrome Colab notebook tab for live verification, not the stale disconnected Local UI tab.
- Confirmed the Colab runtime was connected to an L4 GPU backend and the `HF_TOKEN` secret was configured with notebook access enabled and hidden.
- Ran the notebook setup path: repository install completed, MotionJSON UI launched in the notebook iframe, and the deterministic `examples/demo_red_ball.mp4` fixture was generated.
- Live UI verification blocked before model setup: registering the demo video from the Colab iframe returned `404 page not found`.
- Fixed the frontend URL handling defect that caused Colab-proxied iframe API and asset requests to target the wrong root path.

## Findings

- The Colab iframe rendered the Local UI and displayed `Local API ready`, but form actions using root-relative `/api/...` URLs could resolve outside the port-proxy path in Colab.
- The direct `serve_kernel_port_as_window` URL opened as `404 page not found`, matching the notebook warning that this route may stop working under browser security changes.
- The existing downloaded package at `/Users/edwintse/Downloads/content-test-result` is a pre-fix export:
  - `preview/index.html` still calls `./scene_graph.json`;
  - `package_manifest.json` does not include `previewTools`;
  - the dedicated preview tool files are present.
- Because the UI video-registration step failed, real SAM2/SAM3 extraction was not started. This is a setup blocker, not a model-result failure.

## Changed files

- `src/motionjson/ui/static/app.js`
  - Added `localApiUrl()` to resolve `/api/...` calls relative to the UI route.
  - Routed `fetch()`, asset URLs, and review-tool review/export links through that helper.
  - Preserves normal local URLs as `/api/...`, while Colab-style `/proxy/8766/ui/` paths become `/proxy/8766/api/...`.
- `scripts/test_ui_config_builder.mjs`
  - Added regression coverage for Colab proxy URL resolution and normal local URL resolution.

## Tests run

- `npm test`
- `npm run embed:smoke`
- `npm run build`
- `python3 -m pytest tests/test_local_ui_api.py tests/test_final_export.py -q`

All listed tests passed.

## Chrome evidence

- Colab tab: `colab_ui_provider_connect_demo.ipynb - Colab`.
- Runtime status observed: Python 3 Google Compute Engine backend with L4 GPU; GPU RAM meter visible; Local UI iframe reported `Local API ready`.
- Notebook cell 1 completed `pip install -e ".[ui]"`.
- Notebook cell 4 generated `examples/demo_red_ball.mp4`.
- UI video-registration attempt surfaced `404 page not found`.
- Direct Colab-served UI window URL also returned `404 page not found`.

## Known limitations

- Computer Use stopped returning Chrome window state after the Colab proxy failure, so I could not apply the patch inside the live Colab checkout from this run.
- The live SAM2/SAM3 setup and extraction items remain unverified until the patched UI is available in the Colab runtime.
- The downloaded `/Users/edwintse/Downloads/content-test-result` package remains an old artifact unless manually patched or regenerated.

## Follow-ups

- Pull or apply this UI URL fix in the Colab runtime, restart the Local UI cell, and retry demo video registration.
- After video registration succeeds, continue the bounded SAM2 local and SAM3 Scene Sweep setup/extraction checks.
- Re-export the imported result package so `preview/index.html` and `package_manifest.json` reflect the current exporter behavior.
