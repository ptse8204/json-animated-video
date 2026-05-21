# MotionJSON Release Notes

## Release candidate scope

This release candidate covers the CPU/no-model local workflow and validated
handoff path across CLI, local UI, provider diagnostics, review, correction,
and export. Heavyweight ML providers remain optional and capability-gated.

## Highlights

- API-first object discovery workflow: Clean discovery is the default,
  candidates are returned by the backend review API, users select desired
  candidates, the backend tracks selected objects, and selected-object exports
  stay review-gated.
- Advanced discovery presets: Maximum Recall increases keyframes/candidates
  for missed objects, while Trace Everything is expert/experimental, capped,
  cost/noise acknowledged, and review-required.
- Local UI workflow for choosing tracing goals: one object, text-driven object
  discovery, moving objects, all visible segments, external masks, and review of
  existing MotionJSON output.
- Guided Local UI setup now includes nontechnical project/video setup, goal
  cards, provider/privacy status, model setup, plan confirmation, review,
  correction, and export handoff without requiring CLI knowledge.
- Server-side model planning connector contracts include deterministic fake
  planning and an optional OpenAI planner that remains hosted-call gated,
  redacted, and validated as a proposed run plan rather than extraction truth.
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
- Optional SAM2 automatic proposals provide the practical lower-cost local
  provider path when SAM2 package/checkpoint/config/device diagnostics pass.
  Optional SAM3 local/hosted modes cover concept, exemplar, and higher-recall
  discovery behind capability and hosted opt-in gates.
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
- Hosted provider setup checks do not send frames. Hosted SAM3 smoke tests and
  hosted discovery runs require explicit network, hosted, and cost/privacy
  acknowledgement before any frame leaves the machine.
- Hosted OpenAI/OpenRouter planning and hosted SAM-style providers require
  server-side configuration, hosted-call opt-in, and per-request cost/privacy
  acknowledgement. No model API keys are sent to browser code.
- Raster-only output is surfaced through review diagnostics instead of being
  silently treated as successful vector/object extraction.
- Asset Library and creator-pack workflows use existing local assets and rights
  metadata. They do not create a public marketplace, billing flow, or hosted
  commerce surface in this release candidate.

## License

MotionJSON is licensed under the Apache License, Version 2.0. See the root
`LICENSE` file and package metadata.

Generated MotionJSON output remains subject to the user's source-media rights,
attribution, creator approval, provider terms, and export metadata. The project
license does not grant rights to third-party videos, images, model checkpoints,
provider outputs, or other media supplied by users.

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
python3 scripts/capture_docs_assets.py --check
npm run ui:layout -- --screenshot-dir docs/design/screenshots/release-candidate
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures whole_frame_regression --modes external --out /tmp/motionjson-phase14-benchmark --width 64 --height 48 --frames 4
```
