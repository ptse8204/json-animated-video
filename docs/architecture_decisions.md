# Architecture Decisions

## ADR-0001 — Product is object-layer editing, not universal video-to-JSON

Decision:
MotionJSON will represent video edits as object-layer JSON, but will not claim to convert arbitrary video into pure JSON/SVG/Lottie.

Rationale:
Photorealistic video is best represented as compressed raster/video assets. JSON should store edit state, timing, identity, interaction states, and render instructions.

## ADR-0002 — Photoreal objects remain raster/alpha by default

Decision:
The safe default output for real-world objects is raster/alpha media plus JSON motion metadata.

Rationale:
Texture, blur, shadows, reflections, and fine edges do not vectorize reliably.

## ADR-0003 — OpenRouter is for LLM routing, not segmentation

Decision:
Use OpenRouter-compatible abstractions for LLM/VLM reasoning tasks, but do not bind object masks to OpenRouter.

Rationale:
Segmentation and matting require dedicated pixel models and may be local, hosted, or imported as external masks.

## ADR-0004 — AI should run at ingest/correction, not during normal transform editing

Decision:
Normal drag/scale/rotate/opacity edits should operate on cached assets and JSON transforms.

Rationale:
This supports fast preview, cost control, and resource-aware rendering.

## ADR-0005 — Every phase ends with a git commit

Decision:
The roadmap is implemented in committed phase increments.

Rationale:
This gives reliable rollback, review boundaries, and Codex-controllable progress.
