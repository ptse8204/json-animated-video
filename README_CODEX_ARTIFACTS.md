# MotionJSON Codex Artifacts

Copy these files into the root of `json-animated-video`, then start Codex from that repo root.

## Install

```bash
unzip motionjson-codex-artifacts.zip -d .
git status
```

Then start Codex from the repository root and begin with Phase 0.

## Intended Codex flow

Codex should begin with **Phase 0 only**.

The Master Agent must:
1. Read `AGENTS.md`.
2. Use the configured custom subagents.
3. Run planner → executor → reviewer for the phase.
4. Stop if any subagent reports a concern.
5. Run tests or documented validation commands.
6. Commit at the end of the phase.
7. Only then proceed to the next phase.

## Important product framing

Do not build “video to JSON” as the product.

Build:

```text
AI object-layer editing and web-motion asset generation.
```

Photorealistic objects should remain raster/alpha assets controlled by JSON. SVG/Lottie are optional exports for vector-like silhouettes, labels, outlines, icons, and flat motion graphics.
