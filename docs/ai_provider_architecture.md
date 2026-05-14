# AI Provider Architecture

## Goal

MotionJSON uses AI object-layer editing for video and web graphics. AI should help at ingest, correction, labeling, and optimization time, then editing and preview should run from cached raster/alpha assets and JSON transforms.

Phase 2 defines swappable provider interfaces without changing the local MVP pipeline. The current CLI mask modes remain available, and photoreal objects remain raster/alpha by default. SVG/Lottie remains limited to simple vector-like silhouettes, labels, annotations, icons, and flat graphics.

## Phase 2 Boundaries

Included:

- Provider protocols for LLM, segmentation, matting, render, storage, and export.
- Deterministic mock providers for CI and local tests.
- Optional OpenRouter LLM/VLM provider for reasoning tasks only.
- Segmentation adapters that let existing `MaskProvider` classes participate in the new `SegmentationProvider` abstraction.
- `.env.example` placeholders with no secrets.

Not included:

- Real SAM2, local GPU, or hosted segmentation implementation.
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

Dedicated segmentation options may later include SAM2, local GPU models, hosted segmentation APIs, external masks, Replicate, RunPod, Roboflow, or custom models. OpenRouter is not a segmentation engine.

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

The SAM2 path remains a stub unless a concrete client is injected. OpenRouter is never used as a mask provider.

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
HOSTED_SEGMENTATION_URL=
HOSTED_SEGMENTATION_API_KEY=

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
