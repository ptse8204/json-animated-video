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
  "discovery": {"mode": null, "config": {}},
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

- Provider names are the current CLI providers: `external`, `threshold`,
  `motion`, `mock`, `sam2`, `sam2-local`, and `sam2-hosted`.
- Discovery modes are separate from mask providers: `manual_prompt`,
  `auto_object_proposals`, `sam_auto_masks`, `text_detector`,
  `class_detector`, `motion_foreground`, and `external_masks`.
- `auto_object_proposals` is the API-first default discovery mode for object
  galleries. Its `discovery.config` is normalized into camelCase fields and
  accepts snake_case aliases for API and CLI compatibility. The default clean
  preset is low-cost and review-gated:

```json
{
  "discovery": {
    "mode": "auto_object_proposals",
    "config": {
      "qualityPreset": "clean",
      "intent": "discover_objects_clean",
      "providerPreference": "auto",
      "keyframePolicy": "scene_changes",
      "maxKeyframes": 3,
      "frameInterval": null,
      "maxCandidatesPerKeyframe": 32,
      "maxObjects": 12,
      "minMaskArea": 96,
      "maxMaskAreaRatio": 0.45,
      "dedupeIou": 0.78,
      "stabilityThreshold": 0.86,
      "trackSelectedOnly": true,
      "requireReview": true,
      "writeRejectedCandidates": true
    }
  }
}
```

- `qualityPreset` accepts `clean`, `balanced`, `maximum_recall`, or
  `trace_everything`. Clean, balanced, and maximum recall default
  `trackSelectedOnly` to `true`; Trace Everything sets `trackSelectedOnly` to
  `false`, `trackTopCandidates` to `true`, keeps `requireReview` enabled, and
  requires `costWarningAcknowledged: true`. Trace Everything remains bounded:
  `maxKeyframes <= 24`, `frameInterval <= 600`,
  `maxCandidatesPerKeyframe <= 256`, and `maxObjects <= 128`.
- With `discovery.config.mock: true`, `auto_object_proposals` runs without
  model files, GPU, credentials, or network access. The mock provider writes
  deterministic accepted and rejected candidates plus mask/preview artifacts so
  API and UI review flows can be tested in CI.
- With `discovery.config.providerPreference: "sam2-local"` or `"auto"` and no
  mock flag, `auto_object_proposals` uses the optional local SAM2 automatic
  proposal adapter. The adapter reads `SAM2_LOCAL_CHECKPOINT`,
  `SAM2_LOCAL_CONFIG`, and optional `SAM2_LOCAL_DEVICE`, or the additive config
  keys `sam2Checkpoint`, `sam2ModelConfig`, and `sam2Device`. Missing SAM2,
  torch, checkpoint, config, or automatic-mask support fails clearly in
  diagnostics and job logs.
- `sam3_concept`, `sam3_exemplar`, and `sam3_auto_masks` are optional SAM3
  discovery modes. With `discovery.config.mock: true`, they run without SAM3,
  GPU, hosted credentials, or network access and write normal candidate review
  artifacts. Real local SAM3 execution remains capability-gated behind SAM3
  setup and accepts additive config keys such as `sam3ModelPath`,
  `sam3Device`, `useVideoSession`, `concept`, `exemplars`, and `box`.
  Hosted SAM3 can be requested with `providerPreference: "sam3-hosted"` or
  `hosted: true`, plus `hostedProfile` for `roboflow-sam3-pcs`,
  `fal-sam3-image`, or `custom-sam3-compatible`. It requires `allowNetwork:
  true` and `acknowledgeCostPrivacy: true`; credentials are read from
  server-side settings or environment variables such as `ROBOFLOW_API_KEY`,
  `FAL_KEY`, or `SAM3_HOSTED_API_KEY`. Diagnostics should show missing SAM3,
  Python/CUDA runtime, model setup, endpoint/auth, optional SDKs, or hosted
  opt-in instead of falling back silently. Do not put hosted API keys in run
  configs.
- `class_detector` accepts `discovery.config.class_preset` values
  `common_objects`, `people`, `vehicles`, `animals`, `sports`, or `custom`;
  repeat `--discovery-class` for custom labels and use
  `--discovery-class-preset` from the CLI.
- Prompt boxes use the existing CLI format `x,y,w,h`.
- `sam2-local` and `sam2-hosted` require a point or box prompt in the config.
- Hosted SAM2 config can include `provider.sam2.hosted_config.profile` or
  `provider.sam2.hosted_config.hostedProfile`, for example
  `replicate-sam2-video` or `custom-sam2-compatible`. It stores profile/model
  selection without token values.
- `sample_fps <= 0` remains accepted for CLI compatibility and keeps the current source-FPS sampling behavior.
- Provider capability checks and CUDA/model diagnostics are available through
  `python3 -m motionjson.cli backend diagnostics --json`; see
  [Provider capabilities and diagnostics](provider_capabilities.md).
- Extraction writes `run_config.json` into each output directory as part of the
  local job artifact set; see [Job artifacts and progress](job_artifacts.md).
- The local UI Phase 8 wizard generates this same schema and validates it via
  `POST /api/run-config/validate` before users save or queue work.
