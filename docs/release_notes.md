# MotionJSON Release Notes

## Release candidate scope

This release candidate covers the CPU/no-model local workflow and validated
handoff path across CLI, local UI, provider diagnostics, review, correction,
and export. Heavyweight ML providers remain optional and capability-gated.

## Highlights

- Local UI workflow for choosing tracing goals: one object, text-driven object
  discovery, moving objects, all visible segments, external masks, and review of
  existing MotionJSON output.
- Provider capability reporting through the UI and CLI, including missing CUDA,
  missing SAM2, FFmpeg, detector, and model-weight diagnostics.
- Mock/no-model extraction path for UI smoke tests and CPU-only development.
- Review surfaces for object tracks with label, color, visibility, confidence,
  frame coverage, source provider, export inclusion, and fallback diagnostics.
- Correction actions for relabel, visibility, export inclusion, split, merge,
  delete, add-object hooks, and no-model repair hooks.
- Validated MotionJSON export presets with manifest, validation report, preview
  overlay, contours, masks when requested, and a self-contained ZIP bundle.
- Mock/no-model discovery workflows for text-guided candidates, automatic
  object proposals, motion-only discovery, and detector class presets. Real
  text/class/automatic-mask providers require optional packages, models, and
  configuration.
- Export quality routing, source rights and lineage warnings, and the local
  Asset Library for reusable motion layers, brand collections, and rights-gated
  creator-approved pack metadata. This is not a hosted marketplace or commerce
  launch.
- Synthetic benchmark fixtures for red-ball, multi-object, occlusion,
  small-object, camera-motion, and whole-frame regression checks.

## Compatibility

- Existing CLI entry points remain supported.
- Heavy ML dependencies are not required for the default install.
- Local UI and API responses redact local filesystem paths and storage keys from
  public payloads.
- Raster-only output is surfaced through review diagnostics instead of being
  silently treated as successful vector/object extraction.
- Asset Library and creator-pack workflows use existing local assets and rights
  metadata. They do not create a public marketplace, billing flow, or hosted
  commerce surface in this release candidate.

## Release gate

Before tagging this candidate, run:

```bash
python3 -m pip install -e ".[dev]"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q
npm test
npm run lint
npm run build
python3 scripts/capture_docs_assets.py --check
python3 -m build --sdist --wheel
npm pack --dry-run --workspace @motionjson/runtime
npm pack --dry-run --workspace @motionjson/sdk
docker build -t motionjson-ga .
docker run --rm motionjson-ga python -m motionjson.cli backend diagnostics --json
docker compose config
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures whole_frame_regression --modes external --out /tmp/motionjson-phase14-benchmark --width 64 --height 48 --frames 4
```
