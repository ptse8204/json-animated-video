# UI-WORKFLOW-14 Phase Report - Raster Acceleration Telemetry

## Summary

UI-WORKFLOW-14 completes the Phase 6 speed/runtime slice without changing the
Local UI layout. Raster alpha prep, crop extraction, feathering, cutout
generation, template-match fallback, and vector pre-contour maps now share a
single CPU/CUDA/MPS capability resolver. The pipeline emits the selected
backend, fallback reason, and per-stage elapsed timings so the run monitor can
show useful progress while object masks and cutouts are being produced.

Final polygon contour extraction remains CPU/OpenCV for stable output shape.
CPU fallback remains the default and is covered by tests.

## Changed Files

- `codex_tasks.yaml`
- `docs/roadmap/phase-ui-workflow-14-report.md`
- `docs/roadmap/ui_model_connector_plan.md`
- `src/motionjson/benchmark.py`
- `src/motionjson/cli.py`
- `src/motionjson/layers.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/pipeline_adapters.py`
- `src/motionjson/raster_accel.py`
- `src/motionjson/vectorize.py`
- `tests/test_provider_pipeline.py`
- `tests/test_raster_acceleration.py`

## Browser Evidence

No browser screenshots were captured for this phase because it does not change
UI layout, cards, typography, responsive behavior, or frontend rendering code.
The visible run-monitor improvement comes through existing job/event data
fields consumed by the UI.

## Tests Run

```bash
python3 -m pytest -q tests/test_raster_acceleration.py
python3 -m pytest -q tests/test_provider_pipeline.py tests/test_benchmark.py
python3 -m pytest -q tests/test_job_artifacts.py tests/test_production_asset_formats.py
python3 -m motionjson.cli --help
python3 -m motionjson.cli benchmark --help
python3 -m motionjson.cli extract /tmp/motionjson-phase6-input.mp4 --out /tmp/motionjson-phase6-extract --mask-provider threshold --max-frames 2 --min-area 1 --label 'Red square' --benchmark --benchmark-iterations 1
git diff --check
```

The extract smoke used a generated local temp video. It wrote
`benchmark_report.json` with the new `raster_acceleration` section and
`scene_graph.json` with run-level `providerPerformance.rasterAcceleration`.

## Known Limitations

- GPU acceleration is capability-gated. CUDA/MPS is used only when the selected
  runtime can actually import torch and see the requested accelerator.
- Small benchmark fixtures can be slower on GPU because tensor transfer
  overhead dominates; the benchmark records timing instead of asserting speedup.
- Candidate filtering remains mostly CPU-side outside existing provider-specific
  postprocess paths.
- Final vector polygon extraction remains CPU/OpenCV by design.

## Follow-Up Tasks

- Add hardware-backed CUDA benchmark evidence once CI or a repeatable local
  CUDA runner is available.
- Extend candidate filtering postprocess to the shared resolver where profiling
  shows it dominates selected-object tracking runtime.
