# MotionJSON Codex Planning Packet

This packet is designed to be copied into the root of the `motionjson` repository and then handed to Codex.
It turns the current problem from a fragile CLI workflow into a phased product/engineering roadmap for a capable UI and a stronger extraction engine.

## Core objective

Build MotionJSON into a local-first video object tracing application that supports multiple extraction approaches:

- Manual single-object tracing with SAM2 point, box, mask, positive point, and negative point prompts.
- Text-guided discovery: detect objects from labels such as `red ball . hand . floor .` and use SAM2 to segment/track them.
- Automatic object proposal: generate many candidate masks on keyframes, filter/merge them, and track the useful objects.
- Common-class detection/tracking: optional YOLO-style detector/segmenter integration for known classes.
- Motion-only discovery: background subtraction / optical-flow / frame-difference based tracing for moving objects.
- Review and correction: split, merge, relabel, delete, repair, and re-run tracks instead of accepting bad raster-only results.
- Export: MotionJSON plus debug previews, masks, contours, SVG/vector overlays, and rendered preview video.

## Suggested repository placement

Copy the files as follows:

```text
motionjson/
  AGENTS.md                         # copy from this packet
  CODEX_MASTER_PROMPT.md            # optional; prompt to paste into Codex
  docs/
    codex_motionjson_prd.md
    codex_motionjson_roadmap.md
    codex_motionjson_architecture.md
    codex_motionjson_ui_spec.md
    codex_motionjson_ml_pipeline_spec.md
    codex_motionjson_quality_benchmarks.md
  .codex/
    config.toml
    agents/
      product_strategist.toml
      repo_archaeologist.toml
      backend_cv_architect.toml
      frontend_ui_engineer.toml
      qa_benchmark_engineer.toml
      docs_devrel_engineer.toml
      release_packaging_engineer.toml
      reviewer.toml
  codex_tasks.yaml
```

## How to use with Codex

1. Copy this packet into the repository root.
2. Start Codex from the repository root.
3. Ask Codex to read `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, and the docs in `docs/`.
4. Paste the contents of `CODEX_MASTER_PROMPT.md` as the first task.
5. Require Codex to work phase-by-phase and create a git commit at the end of every phase.

## Operating principle

The CLI should remain useful, but the UI must become the primary workflow for non-expert users. The UI should not merely assemble command strings. It should expose the actual product concepts: video, project, extraction goal, provider capabilities, object candidates, tracks, confidence, corrections, and exports.

## Commit discipline

Every phase must end with:

```bash
git status --short
git add <changed files>
git commit -m "phase N: <short description>"
```

Before each commit, Codex should run the relevant tests, update documentation, and write a short phase report under `docs/roadmap/phase-N-report.md`.

## Important product call

“Trace every object” is not a single ML operation. The software must let users choose what “object” means:

- semantic objects: people, ball, chair, cup, etc.;
- moving foreground objects;
- every visible segment/mask proposal;
- only objects matching text labels;
- only objects from a known detector class list.

The UI should present these as presets with clear labels, tradeoffs, and expected failure modes.
