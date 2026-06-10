---
historical: true
default_context: false
---

# Phase real-colab-sam-local-model-verification report

## Summary

- Used the existing Chrome Colab notebook and the live Colab Local UI tab, not the stale disconnected Local UI URLs.
- Confirmed the Colab runtime was connected to an L4 GPU backend and the Local UI reported `Local API ready`.
- Used the deterministic `examples/demo_red_ball.mp4` fixture for both real local model paths.
- Verified terminal successful extraction, review, preview tools, and compact MotionJSON export for:
  - `sam2-local` prompted one-object tracing;
  - `sam3-local` / SAM3 Scene Sweep discovery.
- Fixed the live SAM2 blockers found in Colab:
  - official SAM2/Hydra cannot consume an absolute YAML config path directly;
  - the public run config correctly redacts local paths, but the worker must recover the server-side checkpoint/config/device values before invoking SAM2;
  - the official SAM2 video predictor expects a frame directory, so MP4 inputs are materialized into temporary numbered JPEG frames.

## Findings

- SAM2 setup correctly surfaced missing local checkpoint/config as setup blockers before any extraction run.
- After SAM2 was installed and the UI restarted, the first real SAM2 run failed terminally with a Hydra config lookup error. The root cause was passing an absolute config YAML path into `build_sam2_video_predictor`; the official package expects a package-relative `configs/...` name.
- The next SAM2 run failed terminally because the browser-visible run config carried `[LOCAL_PATH_REDACTED]` for local model paths. The backend now resolves those redacted values from server-side provider settings at execution time.
- After the runtime-path fixes were applied in Colab and locally, SAM2 extracted the prompted object without falling back to a whole-frame raster export.
- SAM3 Scene Sweep loaded from the approved local/cache path, completed warmup on CUDA, discovered candidates, produced object tracks, and filtered background-like candidates in review.
- The review/export tools are present in the Local UI and the full-view routes load package assets through `/api/jobs/{jobId}/preview-files/...`:
  - `canvas_player.html` loaded `sam3_grid_025` from `../web_asset_manifest.json`;
  - `object_selection_workflow.html` loaded cached assets and `scene_graph.json`;
  - `timeline_editor.html` loaded both SAM3 layers from `../scene_graph.json`.

## Changed files

- `src/motionjson/backend/worker.py`
  - Added server-side recovery for redacted SAM2 checkpoint/config/device values before worker execution.
- `src/motionjson/providers/sam2.py`
  - Normalizes absolute SAM2 config file paths to `configs/...` for official SAM2/Hydra builders.
  - Allows package-relative `configs/...` references without requiring a local file existence check.
  - Materializes video-file inputs into temporary SAM2 frame directories and cleans them up on provider close.
- `tests/test_backend_jobs_worker.py`
  - Covers server-side recovery of public redacted runtime values.
- `tests/test_sam2_providers.py`
  - Covers SAM2 config normalization and MP4-to-frame-directory preparation.

Previously committed in this phase:

- `src/motionjson/ui/static/app.js`
  - Added Colab-aware Local API URL resolution for proxied UI/API paths.
- `scripts/test_ui_config_builder.mjs`
  - Added regression coverage for Colab proxy URL resolution and normal local URL resolution.

## Tests run

- `python3 -m pytest tests/test_backend_jobs_worker.py tests/test_sam2_providers.py tests/test_local_ui_api.py tests/test_provider_settings.py -q`
  - Passed: `122 passed`.
- `python3 -m pytest tests/test_backend_jobs_worker.py tests/test_sam2_providers.py -q`
  - Passed after final cleanup: `33 passed`.
- `npm test`
  - Passed: `21 passed`.
- `npm run embed:smoke`
  - Passed with visible canvas pixels.
- `npm run build`
  - Passed.

## Chrome evidence

- Colab tab: `colab_ui_provider_connect_demo.ipynb - Colab`.
- Live UI tab: `https://8766-gpu-l4-s-kkb-ass1a1-pmbpytgwtrc6-a.asia-southeast1-1.prod.colab.dev/ui/`.
- Runtime status observed: L4 GPU runtime, Python 3, Local UI ready.
- SAM2 final successful run:
  - job id `825a7e554dd1494297ffd343975f617c`;
  - provider `SAM2 local`;
  - status `succeeded`, phase `complete`, progress `100%`;
  - artifacts `188`, objects `1`;
  - job center returned to `0 active` with no stale `running` chip;
  - review showed `1/1 kept`, `1 track`, `1 marked for export`;
  - export generated a compact MotionJSON package.
- SAM3 final successful run:
  - job id `b9e413182d054494bf27d7757dc84604`;
  - provider `SAM3 local`;
  - status `succeeded`, phase `complete`, progress `100%`;
  - extraction artifacts `3488`, objects `2`;
  - reviewed export artifacts `3498`;
  - job center returned to `0 active` with no stale `running` chip;
  - review showed `2/64 kept`, `2 tracks`, `1 marked for export`;
  - export validation passed with `0 issues across 2 checked documents`;
  - compact MotionJSON export generated.
- Preview tool evidence:
  - Canvas player rendered the SAM3 red-ball layer and reported `Loaded sam3_grid_025 from ../web_asset_manifest.json`.
  - Object selection workflow loaded cached assets and reported `2 object, 48 frames`.
  - Timeline editor rendered both layers and reported `Loaded point grid 25 from ../scene_graph.json`.

## Known limitations

- The Colab runtime was patched in-place to continue live verification before the local commit existed. A fresh Colab runtime must pull this commit or re-run the notebook setup from the updated checkout.
- Earlier failed SAM2 jobs remain in the Job Center history, but they are terminal `failed` entries with visible diagnostics rather than stale active runs.
- Browser console logs contained extension-injected errors unrelated to MotionJSON. The MotionJSON preview tool pages still loaded their assets and rendered after their normal async load delay.
- Provider diagnostics still report review-needed counts for some runs; those are visible and do not block terminal status, review, or export.

## Follow-ups

- Re-run the notebook from a fresh runtime after pulling the committed changes to confirm no in-place patching is needed.
- Add a small UI affordance to distinguish initial preview-tool loading from failure so the full-view tools do not look stuck during their first few seconds.
- Continue using `/Users/edwintse/Downloads/content-test-result` as a secondary imported-result regression fixture when validating exported packages.
