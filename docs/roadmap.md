# MotionJSON Long-Horizon Roadmap

## Product destination

MotionJSON is an AI object-layer video editing and web graphics platform.

Core user flow:

```text
upload short video
→ select object
→ AI extracts/tracks object
→ system creates reusable motion layer
→ user edits layer through JSON-controlled scene graph
→ user exports video, website package, or API asset
```

## Roadmap phases

### Phase 0 — Repo governance and agent system

Deliver:
- `AGENTS.md`
- `.codex/config.toml`
- `.codex/agents/motionjson_planner.toml`
- `.codex/agents/motionjson_executor.toml`
- `.codex/agents/motionjson_reviewer.toml`
- `docs/roadmap.md`
- `docs/phase_gates.md`
- `docs/architecture_decisions.md`

Commit:

```bash
git commit -m "phase 0: add governance, roadmap, and Codex agent system"
```

### Phase 1 — Solidify MotionJSON core schema

Deliver JSON schemas, validation utilities, schema docs, and schema validation tests.

Commit:

```bash
git commit -m "phase 1: formalize MotionJSON schemas and validation"
```

### Phase 2 — AI provider abstraction

Deliver LLMProvider, SegmentationProvider, MattingProvider, RenderProvider, mock providers, OpenRouter LLM provider, `.env.example`, and AI architecture docs.

Commit:

```bash
git commit -m "phase 2: add swappable AI provider architecture"
```

### Phase 3 — Real SAM2-compatible segmentation path

Deliver SAM2 local provider, hosted SAM2 provider, optional Replicate/RunPod stubs, mask cache, fake SAM2 integration tests, and docs.

Commit:

```bash
git commit -m "phase 3: integrate SAM2-compatible segmentation providers"
```

### Phase 4 — Object-click web UI prototype

Deliver upload UI, video preview, click/box object selection, extraction job status, extracted object preview, and scene graph viewer.

Commit:

```bash
git commit -m "phase 4: add object selection web UI and extraction workflow"
```

### Phase 5 — Resource-optimized asset formats

Deliver production output mode, transparent WebM export, WebP sprite atlas export, optional AVIF support, and resource comparison in profile.

Commit:

```bash
git commit -m "phase 5: add production asset formats and resource profiling"
```

### Phase 6 — WebGL/PixiJS runtime

Deliver runtime package, Canvas2D runtime, WebGL/PixiJS runtime, React component, plain JS embed, and hover/click/scroll states.

Commit:

```bash
git commit -m "phase 6: add web graphics runtime and embed components"
```

### Phase 7 — Timeline editor MVP

Deliver timeline, layer panel, drag/scale/rotate, opacity, z-index, duplicate/reuse object, and background replacement.

Commit:

```bash
git commit -m "phase 7: build timeline editor for reusable object layers"
```

### Phase 8 — Final render/export system

Deliver FFmpeg export, Remotion export if appropriate, MP4 export, transparent WebM object export, and website package ZIP.

Commit:

```bash
git commit -m "phase 8: add final rendering and export pipeline"
```

### Phase 9 — Quality engine

Deliver mask drift score, edge quality score, missing frame score, occlusion risk score, vector suitability score, and production readiness score.

Commit:

```bash
git commit -m "phase 9: add extraction quality scoring and routing"
```

### Phase 10 — Mask refinement and correction loop

Deliver add/remove prompt point, box correction, brush refine, temporal smoothing, and correction propagation.

Commit:

```bash
git commit -m "phase 10: add mask correction and refinement workflow"
```

### Phase 11 — Multi-object extraction

Deliver multiple objects, object IDs and labels, independent layers, multi-object rendering, and separate export per object.

Commit:

```bash
git commit -m "phase 11: support multi-object extraction and editing"
```

### Phase 12 — SaaS backend

Deliver auth, projects, jobs, assets, queues, storage, workers, and usage tracking.

Commit:

```bash
git commit -m "phase 12: add SaaS backend, jobs, storage, and projects"
```

### Phase 13 — Commercial safety and rights layer

Deliver rights metadata, source attribution, license field, asset lineage, audit log, and commercial-use flag.

Commit:

```bash
git commit -m "phase 13: add rights metadata, attribution, and asset lineage"
```

### Phase 14 — Website graphics productization

Deliver website hero templates, ecommerce templates, education templates, Webflow/Framer-style snippets, and React embeds.

Commit:

```bash
git commit -m "phase 14: productize website motion graphics workflows"
```

### Phase 15 — API product

Deliver REST API, SDK, API keys, webhooks, asset package endpoint, render endpoint, and developer docs.

Commit:

```bash
git commit -m "phase 15: add developer API and SDK"
```

### Phase 16 — Performance and cost optimization

Deliver GPU batching hooks, segmentation cache, provider fallback, cost dashboard, latency metrics, and compression optimizer.

Commit:

```bash
git commit -m "phase 16: optimize inference cost, caching, and asset performance"
```

### Phase 17 — Beta readiness

Deliver closed beta flow, support docs, error reporting, admin dashboard, feedback capture, and privacy docs.

Commit:

```bash
git commit -m "phase 17: prepare closed beta workflow and observability"
```

### Phase 18 — Marketplace / asset library

Deliver saved assets, reusable motion stickers, brand collections, tags/search, license filters, and creator-approved packs.

Commit:

```bash
git commit -m "phase 18: add reusable asset library and marketplace foundation"
```

### Phase 19 — GA launch

Deliver production deployment, billing, pricing plans, public docs, onboarding, security checklist, landing page, and demo gallery.

Commit:

```bash
git commit -m "phase 19: prepare general availability launch"
```
