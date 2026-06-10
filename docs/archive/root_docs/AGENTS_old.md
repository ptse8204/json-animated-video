# MotionJSON Agent Instructions

## Product identity

MotionJSON turns video elements into reusable motion layers for editors and websites.

Do not describe the product as:
- convert all video to JSON
- convert all video to SVG
- convert all video to Lottie

Correct description:
- AI object-layer editing for video and web graphics
- reusable motion layers controlled by JSON
- cached raster/alpha assets for photoreal objects
- SVG/Lottie only for simple vector-like silhouettes, labels, annotations, icons, and flat graphics

## Technical principles

1. AI should run mainly at ingest, correction, labeling, and optimization time.
2. Editing and preview should use cached assets and JSON transforms.
3. Do not rerun AI during normal drag/scale/rotate preview.
4. Keep photoreal objects raster/alpha by default.
5. Keep provider interfaces swappable.
6. Do not hardcode paid API calls.
7. Do not commit secrets.
8. Every phase must have tests or a documented validation command.
9. Every phase must end with a git commit.
10. The master agent may not proceed to the next phase until planner, executor, and reviewer all return PASS / NO CONCERNS.

## Required provider abstractions

- LLMProvider
- SegmentationProvider
- MattingProvider
- RenderProvider
- StorageProvider
- ExportProvider

OpenRouter may be used for LLM/VLM model routing.
OpenRouter is not the pixel segmentation engine.
SAM2/local/hosted segmentation providers must remain separate from LLM providers.

## Test policy

Run relevant tests before every phase commit.

Default:

```bash
pytest -q
```

If frontend exists:

```bash
npm test
npm run lint
```

If rendering/export changes:

```bash
python -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo --mask-provider threshold --max-frames 12
```

If tests are unavailable for a documentation-only phase, run:

```bash
find docs -type f -name "*.md" -maxdepth 2
git diff --check
```

## Commit policy

Every phase ends with:

```bash
git status
pytest -q || true
git diff --check
git add .
git commit -m "phase N: <phase name>"
```

If `pytest -q` fails, do not commit unless the reviewer explicitly confirms the failure is pre-existing or irrelevant to a documentation-only phase.

Do not advance phases without a commit.
