# Multi-Object Extraction

Phase 11 treats `scene_graph.json` as the authoring source of truth for one or more reusable motion layers. Each object keeps a stable ID, label, cached raster/alpha cutouts, masks, motion frames, rights metadata, and one editable layer with independent z-index and JSON transforms.

Deterministic local extraction uses one external mask directory per object:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/multi_demo \
  --object-mask-dir ball=/path/to/ball_masks \
  --object-label ball=Ball \
  --object-mask-dir shadow=/path/to/shadow_masks \
  --object-label shadow=Shadow \
  --max-frames 12
```

For a deterministic local sample, generate the Phase 12 multi-object fixture
and reuse its mask directories:

```bash
python3 -m motionjson.cli benchmark --fixtures multi_object --modes external --out out/benchmarks
python3 -m motionjson.cli extract out/benchmarks/fixtures/multi_object/video.mp4 \
  --out out/demo_multi_object \
  --object-mask-dir red_ball=out/benchmarks/fixtures/multi_object/masks/red_ball \
  --object-label red_ball="Red ball" \
  --object-mask-dir blue_block=out/benchmarks/fixtures/multi_object/masks/blue_block \
  --object-label blue_block="Blue block" \
  --max-frames 6
```

The first object remains the compatibility/default object. The extractor continues to write root `object_motion.json` and `web_asset_manifest.json` aliases for that object, and also writes per-object artifacts:

- `objects/<object_id>/object_manifest.json`
- `objects/<object_id>/object_motion.json`
- `objects/<object_id>/web_asset_manifest.json`

Runtime preview and final rendering use cached assets plus JSON transforms only. Normal drag, scale, rotate, opacity, visibility, clip, and z-index edits do not invoke segmentation, matting, LLM, VLM, or network providers.

Validation:

```bash
pytest -q tests/test_mvp_contract.py
npm test
python3 -m motionjson.cli validate out/multi_demo --object-id ball
```
