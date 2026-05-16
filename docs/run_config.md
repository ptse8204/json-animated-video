# Extraction Run Config

MotionJSON extraction runs now have a typed, JSON-serializable config model in `motionjson.config`. The config is data-only: it stores provider names and settings, but it does not import SAM2, check CUDA, instantiate providers, read secret values, or make network calls.

The CLI still accepts the existing `motionjson extract` flags. Phase 1 builds an `ExtractionRunConfig` internally from those flags before calling the existing provider and pipeline code. A public `--config` flag is intentionally deferred until config-file execution is wired and documented in a later phase.

## Minimal Example

```json
{
  "schema": "motionjson.extraction_run_config.v0.1",
  "input": {"path": "examples/demo_red_ball.mp4"},
  "output": {"directory": "out/demo"},
  "objects": [{"object_id": "object_0", "label": "red ball"}],
  "sampling": {"sample_fps": 12.0, "max_frames": 80},
  "provider": {
    "name": "threshold",
    "threshold": {"lower_hsv": [0, 80, 80], "upper_hsv": [12, 255, 255]},
    "external": {"mask_dir": null},
    "sam2": {
      "checkpoint": null,
      "model_config": null,
      "device": null,
      "prompt_frame": 0,
      "endpoint": null,
      "auth_env": "HOSTED_SEGMENTATION_API_KEY",
      "endpoint_env": "HOSTED_SEGMENTATION_URL",
      "hosted_config": {},
      "hosted_allow_network": false
    },
    "cache": {"enabled": true, "directory": ".motionjson-cache/masks"},
    "fallback_mask_provider": null
  },
  "prompts": [],
  "filters": {"min_area": 100.0, "simplify_ratio": 0.006},
  "export": {
    "output_mode": "authoring",
    "feather": 0,
    "layer_padding": 4,
    "sprite_format": "webp",
    "production_avif": false
  },
  "debug": {"benchmark": false, "benchmark_iterations": 3},
  "rights": {
    "source_type": "user_upload",
    "source_uri": null,
    "source_asset_id": null,
    "display_text": "User uploaded source video",
    "license": "user_uploaded_unverified",
    "license_name": "User uploaded - rights unverified",
    "license_url": null,
    "license_scope": "unknown",
    "creator_approved": false,
    "creator_approval_status": null,
    "commercial_use": false,
    "commercial_use_status": null
  }
}
```

## Python API

```python
from motionjson.config import (
    ExtractionRunConfig,
    build_extraction_run_config_from_args,
    load_run_config,
    write_run_config,
)
```

Use `build_extraction_run_config_from_args(args)` for the current CLI bridge, or `ExtractionRunConfig.from_dict(...)` / `load_run_config(...)` for JSON config files.

## Validation Notes

- Provider names are the current CLI providers: `external`, `threshold`, `motion`, `sam2`, `sam2-local`, and `sam2-hosted`.
- Prompt boxes use the existing CLI format `x,y,w,h`.
- `sam2-local` and `sam2-hosted` require a point or box prompt in the config.
- Hosted SAM2 config stores auth environment variable names, not token values.
- `sample_fps <= 0` remains accepted for CLI compatibility and keeps the current source-FPS sampling behavior.
- Provider capability checks and CUDA/model diagnostics are available through
  `python -m motionjson.cli backend diagnostics --json`; see
  [Provider capabilities and diagnostics](provider_capabilities.md).
- Extraction writes `run_config.json` into each output directory as part of the
  local job artifact set; see [Job artifacts and progress](job_artifacts.md).
