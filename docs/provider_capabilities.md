# Provider Capabilities And Diagnostics

MotionJSON can run without SAM2, torch, CUDA, hosted segmentation, OpenRouter,
or FFmpeg. Provider diagnostics report what is usable in the current local
environment before a user starts extraction or export.

Use [System requirements](system_requirements.md) for hardware expectations
before installing SAM2/SAM3. Provider settings, environment variables, or model
paths can make a provider `configured`, but only diagnostics should decide
whether it is `runnable`.

## CLI

```bash
python3 -m motionjson.cli backend diagnostics --json
```

For a shorter first-run summary:

```bash
python3 -m motionjson.cli backend diagnostics --text
```

Add a video probe and output-directory writability check when preparing a run:

```bash
python3 -m motionjson.cli backend diagnostics --json \
  --video examples/demo_red_ball.mp4 \
  --output-dir out/demo \
  --sam2-checkpoint checkpoints/sam2.pt \
  --sam2-config configs/sam2.yaml
```

The command emits JSON with schema `motionjson.provider_diagnostics.v0.1`. CLI
diagnostics do not initialize the backend SQLite database, create storage
directories, download models, import SAM2/SAM3, call hosted providers, or read
secret values. They only report whether relevant secret environment variables
are present. For SAM2 model paths, explicit `--sam2-checkpoint` and
`--sam2-config` values take precedence over `SAM2_LOCAL_CHECKPOINT` and
`SAM2_LOCAL_CONFIG`.

The Local UI also passes redacted local provider settings into diagnostics.
That lets `/api/capabilities` report a provider as configured when a user has
saved a BYOK key or hosted endpoint in the Local UI. The response still returns
only presence, source, selected model, and redacted display values; it never
returns raw keys. Saved Local UI credentials are marked `configured_settings_only`
until a concrete runtime adapter consumes them; they should not be treated as
runnable provider execution.

Each provider record keeps the older `available`, `configured`, and `status`
fields, then adds clearer first-run fields:

- `installed`: required local packages for that provider are present.
- `configured`: environment variables, model paths, or provider settings are
  present.
- `runnable`: the provider can execute in the current local workflow without
  another opt-in. Hosted segmentation can be credentialed but still not
  runnable until network use is explicitly enabled.
- `needsCredentials`: secrets or hosted credentials are required.
- `needsGpu`: a GPU is required. Current no-model providers do not need one.
- `needsModelPath` and `modelPaths`: model/checkpoint/config paths required by
  local ML providers.
- `estimatedCost`: `zero_local` for local/free providers and
  `unknown_provider_cost` for hosted/network providers.

## Status Values

- `ready`: usable in this environment.
- `available_cpu_only`: configured and importable, but CUDA is unavailable.
- `missing_dependency`: a required optional package or executable is missing.
- `missing_model`: an environment path is configured but does not point to an
  existing model/config file.
- `not_configured`: credentials, endpoints, model paths, or provider settings
  are absent.
- `configured_settings_only`: a Local UI setting exists, but the runtime
  provider still reads environment variables or explicit constructor settings.
- `needs_network_opt_in`: credentials are present, but hosted/network use was
  not explicitly enabled.
- `invalid_configuration`: a saved URL, model, or credential setting is
  malformed.
- `unsupported_runtime`: optional provider dependencies may be installed, but
  the current Python/runtime version is incompatible with that provider.
- `not_implemented`: planned provider surface exists in the diagnostics model,
  but execution is intentionally deferred to a later phase.
- `unavailable`: retained legacy or unsupported path that should not be chosen
  automatically.

## Provider Names

## Provider Matrix

Use this table before choosing a workflow. "Local/free" means the provider can
run without hosted calls or provider billing when its local dependencies are
installed. "Model weights" means a user must bring a local checkpoint, config,
or detector model before the real backend can run.

| Provider | Local/free | GPU required | Model weights | Credentials | Best for | Common failure modes |
| --- | --- | --- | --- | --- | --- | --- |
| `mock` | Yes | No | No | No | Contributor UI smoke checks and tests when launched with `--debug-mock`. | Mock output is deterministic and should not be mistaken for real segmentation. |
| `threshold` | Yes | No | No | No | Simple color-separated objects such as the red-ball demo. | Lighting shifts, similar colors, or broad HSV ranges can create bad masks. |
| `motion` | Yes | No | No | No | Moving object masks when the object separates from the background. | Camera motion, shadows, and reflections can become foreground. |
| `external` | Yes | No | No | No | Reusing masks from another trusted local tool. | Missing frames, wrong object IDs, or masks that cover the background. |
| `manual_prompt` | Yes | No | No | No | One known object marked by a point, box, or imported mask. | Loose prompts can select a wall, floor, or whole-frame region. |
| `motion_foreground` | Yes | No | No | No | Discovering moving regions before tracking. | Static objects are missed and camera movement can create false candidates. |
| `external_masks` | Yes | No | No | No | Multi-object extraction from prepared mask folders or manifests. | Frame-count mismatches and path mistakes can leave tracks incomplete. |
| `auto_object_proposals` | Local SAM2 when configured; debug mock only for tests | Recommended for real SAM2 use | Yes for SAM2 backend | No | Default clean candidate gallery before selected-object tracking. | Clean misses small objects; recall/Trace Everything can be noisy; missing SAM2 package/checkpoint/config blocks real proposals. |
| `sam2-local` | Local once installed | Recommended for real use | Yes | No | Promptable local segmentation/tracking with SAM2-style models. | Missing SAM2 package, checkpoint, config, CUDA, or an overly broad prompt. |
| `sam2-hosted` | No | No local GPU | No local weights | Yes | Hosted segmentation when a user explicitly accepts cost/privacy tradeoffs. | Missing key, missing optional vendor SDK, missing custom endpoint, no hosted opt-in, or remote errors. |
| `sam3-local` | Local once installed | CUDA expected for official concept/exemplar | Yes for official concept/exemplar | No | Advanced official SAM3 package concept/exemplar workflows. Normal scene sweep should read `sam3-auto-masks`. | Missing official SAM3 package/model for concept/exemplar, Python/CUDA mismatch, or incompatible runtime. This is not the normal `Find everything in scene` blocker. |
| `sam3-hosted` | No | No local GPU | No local weights | Yes | Hosted SAM3-compatible discovery experiments. | Missing key, missing optional vendor SDK, missing custom endpoint, no hosted opt-in, or remote errors. |
| `sam3-concept` / `sam3-exemplar` / `sam3-auto-masks` | SAM3 local or hosted when configured; debug mock only for tests | GPU recommended; CUDA expected for official concept/exemplar | Yes for official concept/exemplar; SAM3 Tracker model id/path for scene sweep | Hosted variants need keys | Concept prompts, exemplar search, and scene-wide proposal review. | Missing SAM3 Tracker/Transformers for scene sweep, missing official SAM3 package/model/runtime for concept/exemplar, hosted key, provider SDK, opt-in, or remote errors. |
| `sam_auto_masks` | Local SAM2 when configured; debug mock only for tests | Recommended for real SAM2 use | Yes for SAM2 backend | No | Proposing visible segments for later review. | Background fragments, duplicate masks, or unavailable SAM2 automatic-mask backend. |
| `text_detector` | SAM3 concept is recommended for text prompts; detector backend optional | Backend dependent | Yes for real backend | Hosted SAM3 needs keys | Text-guided candidate boxes before segmentation. | Missing detector/SAM3 package/model or semantically wrong boxes. |
| `class_detector` | Optional detector backend; debug mock only for tests | Future backend dependent | Yes for real backend | No | Known classes such as people, vehicles, or custom local labels. | Missing YOLO-style backend, too many candidates, or wrong class selection. |
| `openrouter` | No | No local GPU | No local weights | Yes | Optional LLM/VLM reasoning or label help. | Missing key/base URL, hosted cost/privacy concerns, and no pixel segmentation capability. |

Current no-model providers:

- `threshold`
- `motion`
- `external`
- `mock`

These report `estimatedCost.status: zero_local` when runnable.

Optional SAM2/hosted providers:

- `sam2`: legacy stub retained for CLI compatibility; it fails clearly unless a
  test/client injects behavior.
- `sam2-local`: local SAM2-compatible segmentation; requires optional SAM2,
  torch, `SAM2_LOCAL_CHECKPOINT`, and `SAM2_LOCAL_CONFIG`.
- `sam2-hf-auto-masks`: SAM2 HF automatic-mask fallback for
  everything-in-scene discovery; uses `facebook/sam2.1-hiera-large` through
  Transformers and does not require the official `sam2` package, SAM2
  checkpoint, or SAM2 config.
- `sam2-hosted`: hosted segmentation. `replicate-sam2-video` uses
  `REPLICATE_API_TOKEN` and the optional `replicate` package; custom endpoints
  use `HOSTED_SEGMENTATION_URL` and `HOSTED_SEGMENTATION_API_KEY`. Extraction
  still requires explicit network/cost/privacy opt-in.
- `auto_object_proposals` and `sam_auto_masks`: local SAM2 automatic proposal
  diagnostics require the `sam2.automatic_mask_generator` module, torch, and
  existing `SAM2_LOCAL_CHECKPOINT` / `SAM2_LOCAL_CONFIG` paths. They report
  `available_cpu_only` when configured without CUDA, because CPU execution is
  possible but expected to be slower.
- `sam3-auto-masks`: normal SAM3 Scene Sweep diagnostics. This path uses the
  independent `sam3-transformers` extra, `sam3TrackerModel=facebook/sam3` by
  default, and does not require SAM2, a SAM2 checkpoint/config, the official
  `sam3` package, or `SAM3_LOCAL_MODEL`.
- `sam3-local`: advanced official-package concept/exemplar diagnostics. This
  path requires the optional `sam3` package, Python 3.12+, torch with CUDA
  available, and an existing `SAM3_LOCAL_MODEL` checkpoint file path. A cloned
  source checkout such as `/content/sam3` and the Hugging Face repo id
  `facebook/sam3` are not model paths for `SAM3_LOCAL_MODEL`; use the resolved
  local `sam3.pt` file. The base install and mock modes do not require any of
  those.
- `sam3-hosted`: hosted SAM3-compatible discovery. `roboflow-sam3-pcs` uses
  `ROBOFLOW_API_KEY`, `fal-sam3-image` uses `FAL_KEY` plus the optional
  `fal-client` package, and custom endpoints use `SAM3_HOSTED_URL` and
  `SAM3_HOSTED_API_KEY`. Its setup check is no-network; the smoke test is a
  separate API call that requires a cost/privacy acknowledgement first.

Reasoning provider:

- `openrouter`: optional LLM/VLM reasoning only. It is not a segmentation
  provider.

Provider settings:

- `GET /api/provider-settings` returns the provider/model registry and redacted
  per-user settings.
- `POST /api/provider-settings` saves a provider model choice, endpoint/base
  URL, hosted-call opt-in, or replacement API key.
- `DELETE /api/provider-settings/PROVIDER_ID` clears local settings and saved
  key material for that provider.
- `POST /api/provider-settings/PROVIDER_ID/test` runs a no-network readiness
  check. Hosted providers are checked for required fields and plausible key
  format, but the smoke test does not call the remote provider.
- `POST /api/provider-settings/sam2-hosted/smoke-test` and
  `POST /api/provider-settings/sam3-hosted/smoke-test` run explicit hosted SAM
  smoke tests. They require `allowNetwork: true`, `allowHosted: true`, and
  `acknowledgeCostPrivacy: true`, use server-side settings or environment
  credentials, and redact secrets in all responses.
- `POST /v1/providers/sam2-hosted/smoke-test` and
  `POST /v1/providers/sam3-hosted/smoke-test` expose the same explicit smoke
  tests for authenticated/headless API clients.

Environment variables override Local UI settings. This keeps CLI/headless use
predictable and avoids surprising hosted calls in shared environments. Saved
hosted SAM2/SAM3 keys can be used by the Local UI worker for explicit hosted
extraction. Other hosted reasoning keys remain connector-specific and are still
never exposed to the browser.

Discovery providers:

- `manual_prompt`: no-model user point/box/mask candidate input.
- `auto_object_proposals`: API-first automatic object proposals with clean,
  balanced, maximum-recall, and Trace Everything presets. Mock proposal routing
  remains for smoke checks; local SAM2 automatic proposals become runnable only
  when optional SAM2 diagnostics pass.
- `motion_foreground`: no-model CPU frame-difference moving-region discovery.
- `external_masks`: no-model import of mask directories or manifests.
- `sam_auto_masks`: optional automatic-mask proposals; unavailable until SAM2
  automatic-mask dependencies and model paths are configured.
- `sam3_concept`: SAM3-style text/concept discovery. Mock mode works without
  model setup; real local execution uses the optional SAM3 adapter when
  diagnostics pass.
- `sam3_exemplar`: SAM3-style exemplar/crop discovery. Mock mode works without
  model setup; real local execution uses the optional SAM3 adapter when
  diagnostics pass.
- `sam3_auto_masks`: SAM3 scene sweep. Mock mode works without model setup;
  real local execution uses SAM3 Tracker automatic mask generation on sampled
  keyframes plus SAM3 Tracker Video propagation for accepted candidates. It
  does not use a broad `"object"` concept prompt and it does not require SAM2.
- `text_detector`: optional open-vocabulary detector scaffold. Text prompts
  become detector candidates first and are not routed directly to SAM2.
- `class_detector`: optional known-class detector scaffold. Mock mode supports
  known-class presets for UI and benchmark smoke checks; real YOLO-style
  execution remains unavailable until dependencies and an adapter are wired.

Pipeline providers:

- `video-tracker`: per-frame mask tracking adapter and mock tracks.
- `track-linker`: identity linker with duplicate-ID guard.

Export/vector providers:

- `contour-vectorizer`
- `motionjson-json`
- `website-zip`
- `remotion-plan`
- `silhouette-lottie`
- `ffmpeg-video`

## Interpreting Failures

Diagnostics should be shown before UI or backend jobs run. A missing optional
provider is not fatal when the chosen workflow can use a no-model provider such
as `threshold`, `motion`, `external`, or `mock`. A UI should disable unavailable
choices, keep the reason visible, and offer a no-model workflow when possible.

Do not route text prompts directly to raw SAM2. Text-guided object discovery
must use a detector/candidate provider first, then pass candidate prompts or
masks into segmentation/tracking.
