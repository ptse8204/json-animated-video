# AI Provider Architecture

## Goal

All AI services must be swappable. No product path should be locked to one provider.

## Separate LLM reasoning from pixel segmentation

OpenRouter-style routing is useful for text/vision reasoning tasks:

```text
object labeling
prompt interpretation
template generation
web embed generation
quality explanation
rights/compliance wording
```

It should not be treated as the segmentation engine.

Pixel extraction must use dedicated segmentation/matting providers:

```text
SAM2
local GPU models
hosted segmentation API
external mask import
Replicate
RunPod
Roboflow
custom model
```

## Interfaces

### LLMProvider

```python
class LLMProvider:
    def complete(self, messages, *, model=None, tools=None, response_format=None):
        ...
```

### SegmentationProvider

```python
class SegmentationProvider:
    def prepare(self, video_metadata):
        ...

    def segment(self, frame_index, frame_bgr, *, prompt_point=None, prompt_box=None):
        ...

    def close(self):
        ...
```

### MattingProvider

```python
class MattingProvider:
    def refine_alpha(self, frame_rgb, binary_mask):
        ...
```

### RenderProvider

```python
class RenderProvider:
    def render_preview(self, scene_graph):
        ...

    def export_video(self, scene_graph, output_path):
        ...
```

## Environment variables

Use `.env.example`, never real secrets.

```bash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=openai/gpt-5.2

OPENAI_API_KEY=
OPENAI_DEFAULT_MODEL=gpt-5.5

SEGMENTATION_BACKEND=external
SAM2_LOCAL_CHECKPOINT=
SAM2_LOCAL_CONFIG=
REPLICATE_API_TOKEN=
RUNPOD_API_KEY=
ROBOFLOW_API_KEY=
```

## Provider routing

A future router should support:

```text
provider preference
fallback chain
cost estimates
latency estimates
feature capabilities
local-only mode
no-network mode
```

Example config:

```json
{
  "llm": {
    "primary": "openrouter",
    "fallback": ["openai", "mock"],
    "model": "openai/gpt-5.2"
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

## Rules

- Do not hardcode paid API calls.
- Do not require credentials for tests.
- Provide mock providers for CI.
- Every provider must fail gracefully with actionable error messages.
- Store raw masks in cache so downstream processing is provider-independent.
