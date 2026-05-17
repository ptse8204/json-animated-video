# Benchmark Fixtures

Phase 12 adds a CPU-only benchmark suite for regression checks. It generates
synthetic videos, ground-truth masks, expected-output manifests, extraction
runs, `summary.json`, and `summary.md` without GPU, SAM2 weights, hosted
providers, or network access.

## Command

```bash
python3 -m motionjson.cli benchmark --fixtures synthetic --modes external --out out/benchmarks
```

Useful lightweight CI form:

```bash
python3 -m motionjson.cli benchmark --fixtures red_ball,whole_frame_regression --modes external --out out/benchmarks
```

`--fixtures synthetic` means all built-in fixtures. `--modes threshold` is kept
as an alias for the deterministic `external_masks` reference path, while
`--modes motion` runs the CPU motion-foreground provider and `--modes mock`
runs mock text-detector boxes for comparison. Comparison modes can report
regressed or failed runs for fixtures they are not expected to solve; use
`--fail-on-regression` when CI should fail on any such run.

## Outputs

```text
out/benchmarks/
  summary.json
  summary.md
  fixtures/
    red_ball/
      video.mp4
      fixture_manifest.json
      expected.json
      masks/
  runs/
    red_ball_external_masks/
      scene_graph.json
      tracks.json
      fallback_diagnostics.json
```

`summary.json` is machine-readable and uses
`motionjson.evaluation_benchmark.v0.1`, which is validated by the packaged
MotionJSON schema tools. `summary.md` is the human-readable table for local
review. Reports include duplicate-overlap metrics (`pairCount`, `maxMeanIou`,
and merge-suggestion counts), fallback reasons, continuity, coverage, runtime,
and validation status. Run paths are relative to the benchmark output directory
so reports do not embed machine-specific local paths.

## Built-In Fixtures

- `red_ball`: one red object should be accepted with stable coverage.
- `multi_object`: red circle and blue block should produce two accepted tracks.
- `occlusion`: one partially occluded object should remain accepted.
- `small_object`: one tiny object should be accepted when benchmark `min-area`
  is low.
- `camera_motion`: external-mask mode should keep the object despite background
  motion.
- `whole_frame_regression`: a whole-frame mask must be rejected with
  `masks_too_large_whole_frame`.

## Known Demo Video Behavior

`examples/demo_red_ball.mp4` is the manual red-ball demo. Expected behavior:

- one object track for the red ball in manual/threshold-style workflows;
- no whole-frame mask should be exported as an accepted object track;
- if a provider returns a whole-frame/background mask, logs and UI diagnostics
  should include `masks_too_large_whole_frame`;
- validated MotionJSON export should include one included object unless the
  user explicitly excludes or deletes it in review.

The benchmark fixtures are not replacements for visual QA. They are deterministic
regression inputs for object count, track continuity, mask coverage, duplicate
overlap, fallback reason counts, runtime, and schema validation.
