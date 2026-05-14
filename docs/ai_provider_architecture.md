# AI Provider Architecture

## Goal

MotionJSON uses AI object-layer editing for video and web graphics. AI should help at ingest, correction, labeling, and optimization time, then editing and preview should run from cached raster/alpha assets and JSON transforms.

Phase 2 defined swappable provider interfaces without changing the local MVP pipeline. Phase 3 adds SAM2-compatible segmentation providers behind that interface. The current CLI mask modes remain available, and photoreal objects remain raster/alpha by default. SVG/Lottie remains limited to simple vector-like silhouettes, labels, annotations, icons, and flat graphics.

Phase 16 adds provider performance primitives. Provider attempts, batch hooks,
cache summaries, fallback outcomes, estimated cost units, and compression
outcomes are reported as data. They do not introduce GPU, torch, hosted API, or
paid-provider dependencies.

## Phase 2-3 Boundaries

Included:

- Provider protocols for LLM, segmentation, matting, render, storage, and export.
- Deterministic mock providers for CI and local tests.
- Optional OpenRouter LLM/VLM provider for reasoning tasks only.
- Segmentation adapters that let existing `MaskProvider` classes participate in the new `SegmentationProvider` abstraction.
- Optional local SAM2-compatible segmentation provider with lazy imports and injected fake predictor support.
- Hosted SAM2-compatible segmentation provider with injected client/transport support and no default network calls.
- Mask cache for normalized binary PNG masks under an ignored cache directory.
- Optional batch segmentation request shape for providers that can process
  multiple frames together, with sequential fallback for existing providers.
- Segmentation-provider fallback routing with provider names, primary failures,
  fallback successes/failures, timings, and best-effort close semantics.
- Resource profile cost dashboards for provider/cache/latency/compression data.
- `.env.example` placeholders with no secrets.

Not included:

- SAM2, torch, Replicate, RunPod, or hosted services as default dependencies.
- UI editing tools.
- Final production render/export infrastructure.
- SaaS/backend, marketplace, billing, or API product surfaces.
- Paid API calls in default code paths or tests.

## Provider Abstractions

The canonical interfaces live in `src/motionjson/providers/base.py`.

### LLMProvider

Reasoning provider for text and VLM tasks:

```python
class LLMProvider:
    def complete(self, messages, *, model=None, tools=None, response_format=None, **routing):
        ...
```

Intended tasks include object labeling, prompt interpretation, quality explanation, edit suggestions, rights/compliance wording, and manifest/template reasoning. An `LLMProvider` must not own pixel segmentation.

Phase 2 includes `OpenRouterLLMProvider` and `MockLLMProvider`. Future concrete LLM providers can include OpenAI-compatible, local, or hosted VLM clients behind the same interface.

### SegmentationProvider

Pixel mask provider for ingest/correction-time object extraction:

```python
class SegmentationProvider:
    def prepare(self, video_metadata):
        ...

    def segment(self, frame_index, frame_bgr, *, prompt_point=None, prompt_box=None):
        ...

    def close(self):
        ...
```

Dedicated segmentation options include existing demo providers, external masks, local SAM2-compatible providers, hosted SAM2-compatible providers, and optional credential-gated Replicate/RunPod stubs. OpenRouter is not a segmentation engine.

Batch-capable providers can also implement:

```python
class BatchSegmentationProvider(SegmentationProvider):
    def segment_batch(self, requests):
        ...
```

Each request contains `frame_index`, `frame_bgr`, and optional point/box
prompts. The core project only defines the hook and request shape; GPU batching
is a provider implementation detail. Existing providers are routed through the
same abstraction with sequential fallback.

### MattingProvider

Alpha refinement provider:

```python
class MattingProvider:
    def refine_alpha(self, frame_rgb, binary_mask):
        ...
```

Matting improves cached raster/alpha assets after segmentation. It should not be rerun during normal drag/scale/rotate preview.

### RenderProvider

Preview/render provider:

```python
class RenderProvider:
    def render_preview(self, scene_graph):
        ...

    def export_video(self, scene_graph, output_path):
        ...
```

Render providers consume cached assets and JSON transforms. They should not require AI for normal timeline preview.

### StorageProvider

Storage provider for cached assets and manifests:

```python
class StorageProvider:
    def save_bytes(self, key, data, *, content_type=None):
        ...

    def load_bytes(self, key):
        ...

    def exists(self, key):
        ...
```

Storage implementations should support local development and future hosted object storage without changing scene or asset contracts.

### ExportProvider

Artifact export provider:

```python
class ExportProvider:
    def export(self, scene_graph, output_path, *, format=None):
        ...
```

Export providers package MotionJSON manifests, cached raster/alpha assets, and web/player bundles. Phase 2 only defines the contract and deterministic mocks.

## Segmentation Adapter Strategy

The existing pipeline uses `MaskProvider.prepare()`, `MaskProvider.get_mask()`, and `MaskProvider.close()`. Phase 2 keeps that behavior and adds adapters:

- `MaskProviderSegmentationAdapter` exposes an existing mask provider as a `SegmentationProvider`.
- `SegmentationMaskProvider` lets a `SegmentationProvider` run in the existing extraction pipeline.

This preserves current CLI modes:

```bash
--mask-provider threshold
--mask-provider motion
--mask-provider external
--mask-provider sam2
```

The legacy `sam2` path remains a stub unless a concrete client is injected. Phase 3 adds:

```bash
--mask-provider sam2-local
--mask-provider sam2-hosted
```

`sam2-local` lazy-imports SAM2 only when a predictor or predictor factory is not injected. `sam2-hosted` requires an injected client/transport or explicit network opt-in with endpoint and auth. OpenRouter is never used as a mask provider.

Use `--fallback-mask-provider threshold` or `--fallback-mask-provider motion`
when a primary segmentation provider should fall back to a local deterministic
provider. Fallback routing is segmentation-only. Names such as `openrouter`,
`llm`, and `vlm` are rejected before execution.

## Mask Cache

`MaskCache` lives in `src/motionjson/providers/mask_cache.py`. It stores provider-independent binary PNG masks and a manifest under `.motionjson-cache/masks` by default. Cache keys include provider, config, source video, prompt, object id, and video metadata; per-frame PNG names carry the frame index. The extraction pipeline receives normalized `uint8` arrays with values `0` or `255`.

The cache is an optimization for ingest/correction-time work. Preview and editing still use generated assets and JSON transforms.

`MaskCache.summary()` reports entry count, stored mask count, stored bytes,
hits, misses, hit rate, read bytes, and written bytes. SAM2 providers attach
this summary to provider performance metadata. LLM/OpenRouter paths do not use
the segmentation mask cache.

## Performance And Cost Reports

`ProviderAttempt`, `PhaseTiming`, `BatchSegmentationRequest`, and
`CompressionOutcome` live in `src/motionjson/providers/base.py`. Extraction
outputs surface them through:

- `scene_graph.json`: `providerPerformance`, `latencyMetrics`, and
  `costDashboard`
- `resource_profile.json`: the same provider/cache/latency/cost data plus
  `compressionOptimizer` when production assets are enabled
- backend job events: `latency_metrics` and `cost_dashboard`
- backend usage: provider attempts, cache hits/misses, and latency totals

Local deterministic providers report zero local provider cost. Hosted/custom
providers report explicit unknown cost unless the provider supplies a concrete
cost model. No paid API call is hardcoded by these reports.

## OpenRouter Scope

`OpenRouterLLMProvider` is optional and uses OpenRouter's OpenAI-compatible chat completions shape:

```text
POST /api/v1/chat/completions
Authorization: Bearer <OPENROUTER_API_KEY>
```

It supports `messages`, optional `model`, `tools`, `response_format`, and routing fields. It uses stdlib HTTP by default and accepts an injected transport for tests. It is only for LLM/VLM reasoning and must not be used for pixel segmentation or matting.

## Mock Providers And No-Network Tests

Mock providers live in `src/motionjson/providers/mocks.py`:

- `MockLLMProvider`
- `MockSegmentationProvider`
- `MockMattingProvider`
- `MockRenderProvider`
- `MockStorageProvider`
- `MockExportProvider`

They are deterministic, require no credentials, and make no network calls. Tests for OpenRouter must inject a transport and assert request construction without touching the network.

SAM2 provider tests inject fake predictors or fake hosted clients. They do not import SAM2, torch, Replicate, RunPod, or touch the network.

## Environment Variables

Use `.env.example` for placeholders only:

```bash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=
OPENROUTER_APP_NAME=MotionJSON
OPENROUTER_SITE_URL=

OPENAI_API_KEY=
OPENAI_DEFAULT_MODEL=
LOCAL_LLM_BASE_URL=
LOCAL_LLM_DEFAULT_MODEL=

SEGMENTATION_BACKEND=threshold
SAM2_LOCAL_CHECKPOINT=
SAM2_LOCAL_CONFIG=
SAM2_LOCAL_DEVICE=cpu
HOSTED_SEGMENTATION_URL=
HOSTED_SEGMENTATION_API_KEY=
REPLICATE_API_TOKEN=
RUNPOD_API_KEY=
RUNPOD_SAM2_ENDPOINT_ID=

STORAGE_BACKEND=local
STORAGE_BUCKET=
STORAGE_PREFIX=

EXPORT_BACKEND=local
```

Do not commit secrets. Do not hardcode paid API calls. Provider implementations should fail with actionable messages when required configuration is missing.

## Future Routing

A future router can choose providers by capability, cost, latency, local-only mode, and fallback chain:

```json
{
  "llm": {
    "primary": "openrouter",
    "fallback": ["mock"],
    "model": "openai/example-model"
  },
  "segmentation": {
    "primary": "sam2_local",
    "fallback": ["external_masks", "mock"]
  },
  "matting": {
    "primary": "local_matting",
    "fallback": ["none"]
  }
}
```

Routing must keep LLM providers separate from segmentation and matting providers.
