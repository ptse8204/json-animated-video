# Examples

These examples use local files and deterministic providers unless a section
says otherwise. Start with the no-model examples before enabling SAM2,
detectors, or hosted providers.

## Red-Ball CLI Demo

This is the smallest end-to-end object extraction path. It needs no GPU, no
SAM2, no detector weights, and no cloud API.

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
python3 -m motionjson.cli validate out/demo_red_ball
```

Expected output folder:

```text
out/demo_red_ball/
  artifacts.json
  candidates.json
  events.jsonl
  fallback_diagnostics.json
  frames/
  job.json
  logs.txt
  masks/
  metrics.json
  object_motion.json
  objects/
  preview/
  provider_diagnostics.json
  resource_profile.json
  rights_manifest.json
  run_config.json
  scene_graph.json
  tracks.json
  web_asset_manifest.json
```

Expected behavior: one accepted red-ball object track, threshold masks, cached
cutouts, MotionJSON scene files, and diagnostics. The whole frame should not be
accepted as the object.

![Red-ball preview](assets/canvas-preview-red-ball.png)

![Red-ball mask overlay GIF](assets/red-ball-demo.gif)

## Local UI Mock Smoke Path

Launch the local UI in no-model mode:

```bash
python3 -m motionjson.cli ui --no-open --mock
```

Then create a project, register `examples/demo_red_ball.mp4`, start a mock job,
and review the generated track before export.

![Local UI first-run checklist](assets/local-ui-first-run.png)

![Local UI project setup](assets/local-ui-new-project.png)

![Extraction wizard](assets/local-ui-extraction-wizard.png)

![Provider diagnostics](assets/local-ui-provider-diagnostics.png)

![Job review](assets/local-ui-job-review.png)

The screenshots can be regenerated with:

```bash
python3 scripts/capture_docs_assets.py --check
python3 scripts/capture_docs_assets.py
```

## Multi-Object External-Mask Demo

Use this when you want two known objects from deterministic fixture masks. It
needs no GPU or model weights.

```bash
python3 -m motionjson.cli benchmark --fixtures multi_object --modes external --out out/benchmarks
python3 -m motionjson.cli extract out/benchmarks/fixtures/multi_object/video.mp4 \
  --out out/demo_multi_object \
  --object-mask-dir red_ball=out/benchmarks/fixtures/multi_object/masks/red_ball \
  --object-label red_ball="Red ball" \
  --object-mask-dir blue_block=out/benchmarks/fixtures/multi_object/masks/blue_block \
  --object-label blue_block="Blue block" \
  --max-frames 6
python3 -m motionjson.cli validate out/demo_multi_object --object-id red_ball
python3 -m motionjson.cli validate out/demo_multi_object --object-id blue_block
```

Expected output folder:

```text
out/demo_multi_object/
  candidates.json
  fallback_diagnostics.json
  masks/
  objects/
  scene_graph.json
  tracks.json
  web_asset_manifest.json
```

Expected behavior: two accepted object tracks with stable IDs and no duplicate
overlap rejection.

## Browser Preview

After generating an output folder, serve the repository:

```bash
python3 -m http.server 8080
```

Open the Canvas2D preview:

```text
http://localhost:8080/examples/canvas_player.html?scene=/out/demo_red_ball/web_asset_manifest.json
```

Useful local example files:

- [Canvas player](../examples/canvas_player.html)
- [Plain JavaScript embed](../examples/plain_js_embed.html)
- [Pixi player](../examples/pixi_player.html)
- [Timeline editor](../examples/timeline_editor.html)
- [Object selection workflow](../examples/object_selection_workflow.html)
- [Demo gallery](../examples/demo_gallery.html)

These examples use local imports and generated MotionJSON output. They should
not call SAM2, detectors, hosted segmentation, OpenRouter, or network providers
during preview.

## Website Embed Examples

The runtime docs include copyable snippets for plain JavaScript, Canvas2D,
optional Pixi/WebGL, and React:

- [Runtime guide](runtime.md)
- [Final export](final_export.md)

Common preview URLs after serving the repo:

```text
http://localhost:8080/examples/plain_js_embed.html?manifest=/out/demo_red_ball/web_asset_manifest.json
http://localhost:8080/examples/timeline_editor.html?scene=/out/demo_red_ball/scene_graph.json
http://localhost:8080/examples/website_graphics_hero.html?manifest=/out/demo/web_asset_manifest.json
```

Use `web_asset_manifest.json` for website playback. Use `tracks.json`,
`provider_diagnostics.json`, and `fallback_diagnostics.json` when you need to
understand why tracks were accepted, rejected, or unavailable.
