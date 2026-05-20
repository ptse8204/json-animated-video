# Discovery Providers

Phase 5 adds object-candidate discovery providers for workflows that need more
than one manually selected object. Discovery providers output the shared
`ObjectCandidate` shape first; segmentation/tracking still happens through the
provider pipeline.

SAM2 is promptable segmentation/tracking, not semantic discovery by itself.
Text and class workflows must use detector candidates before a mask/tracker
provider receives boxes or masks.

## Modes

- `manual_prompt`: use when a user marks one or more objects with points,
  boxes, or mask references. No model is required.
- `auto_object_proposals`: default API-first object discovery mode. It uses
  typed quality presets so a clean run can propose fewer reviewable candidates
  before users select objects for tracking. It remains mock/no-model by
  default, with an optional `sam2-local` automatic proposal path when SAM2,
  torch, checkpoint, and model config are configured.
- `motion_foreground`: use for simple footage where moving objects separate
  from a mostly stable background. This CPU mode writes generated mask
  sequences under `discovery/motion_foreground/`.
- `external_masks`: use when masks or boxes already exist from another local
  tool. It imports one candidate per object mask directory or manifest entry.
- `sam_auto_masks`: automatic keyframe mask proposals. It is capability-gated
  behind optional SAM2/torch/model configuration and has a mock mode for tests.
- `sam3_concept`: optional SAM3-style concept discovery from a text phrase.
  Mock mode writes deterministic candidates without SAM3, GPU, credentials, or
  network calls.
- `sam3_exemplar`: optional SAM3-style discovery from exemplar/crop references.
  Mock mode lets the review API and UI exercise exemplar-shaped candidates.
- `sam3_auto_masks`: optional SAM3-style high-recall automatic proposals. Mock
  mode uses the same candidate/rejected-candidate review shape as the default
  object proposal flow.
- `text_detector`: scaffold for open-vocabulary detection. Missing detector
  packages or model paths are capability warnings; mock mode can produce local
  boxes for UI smoke checks.
- `class_detector`: scaffold for known-class detection. Missing optional
  detector packages are reported in diagnostics; mock mode is local-only and
  supports class presets such as `vehicles`, `people`, and `common_objects`.

## When To Use And Failure Modes

| Mode | Use When | Common Failure Mode | Safer Fallback |
| --- | --- | --- | --- |
| `manual_prompt` | One known object needs a point, box, or mask prompt. | Prompt is too loose and returns background or whole-frame masks. | Add a tighter box or use external masks. |
| `auto_object_proposals` | Users should click Discover objects and choose from API-returned candidates. | Clean presets may miss small/occluded objects; recall presets can be noisy. | Start with `clean`, retry with `maximum_recall`, and keep review required. |
| `motion_foreground` | The camera is mostly still and objects move. | Camera motion or shadows become candidates. | Use `external_masks` or review/delete extra tracks. |
| `external_masks` | Masks or boxes already exist from another local tool. | Mask sequence is missing frames or points at the wrong object. | Validate each object ID and inspect `fallback_diagnostics.json`. |
| `sam_auto_masks` | A configured SAM2-style backend should propose visible segments. | Background fragments, floor/wall masks, or missing SAM2 weights. | Use filters, mock mode, or a detector-first workflow. |
| `text_detector` | Users describe objects with text labels. | Detector package/model is missing or boxes are semantically wrong. | Use mock smoke tests, class detector, or manual/external masks. |
| `class_detector` | Known classes are enough for the video domain. | YOLO/known-class model is unavailable or returns too many classes. | Limit classes, lower max candidates, or use manual review. |

## UI vs CLI Support Today

| Workflow | CLI support | Local UI job support |
| --- | --- | --- |
| `manual_prompt` + `threshold`/`external`/`mock` | Runnable with base CPU dependencies. | Runnable through the local worker. |
| `auto_object_proposals` | Runnable when `discovery.config.mock` is `true`, with clean, balanced, and maximum-recall presets. With `providerPreference: "sam2-local"` or `"auto"`, it can use configured local SAM2 automatic masks for keyframe proposals and SAM2 propagation for accepted candidate mask sequences. SAM3 remains a later optional provider family. | Runnable in mock mode through the local worker when `discovery.config.mock` is `true`; with local SAM2 configured, the worker can run API-backed SAM2 proposals and return the same review candidate shape. |
| `motion_foreground` / `motion` | Runnable from the CLI as a CPU/no-model path with frame-difference candidate scores. | Runnable through the local worker; review shows motion candidates, track confidence, fallback diagnostics, and export state. |
| `external_masks` | Runnable when mask directories or a manifest are supplied. | Runnable when the selected local asset has a mask directory configured. |
| `text_detector` | Mock mode is runnable and writes candidate boxes, mask sequences, tracks, and review metadata. Real detector backends remain scaffolded until configured and wired. | Runnable in mock mode through the local worker; review shows `candidate_summary` before track/export decisions. |
| `class_detector` | Mock mode is runnable with `--discovery-class-preset` and repeatable `--discovery-class`; real detector backends are scaffolded until configured and wired. | Runnable in mock mode through the local worker; review shows class-preset candidates, tracks, diagnostics, and export state without claiming real YOLO availability. |
| `sam_auto_masks` | Mock mode is runnable and writes visible-segment candidates, generated mask sequences, track filter/dedupe metadata, and review artifacts. Real automatic masks use the same optional local SAM2 automatic proposal adapter. | Runnable in mock mode through the local worker; with local SAM2 configured, review shows SAM2 proposal candidates, track filtering, fallback diagnostics, and merge suggestions. |
| `sam3_concept` / `sam3_exemplar` / `sam3_auto_masks` | Mock mode is runnable and writes API-first candidates for concept, exemplar, and higher-recall review flows. Real local SAM3 uses the optional adapter only when SAM3, Python 3.12+, CUDA, and `SAM3_LOCAL_MODEL` are configured. Hosted SAM3 can be selected with `providerPreference: "sam3-hosted"` only with explicit network and cost/privacy acknowledgement. | Runnable in mock mode through the local worker; non-mock runs fail clearly unless diagnostics pass or hosted network use is explicitly acknowledged. |

Candidate-producing workflows write `candidates.json`, which is registered as a
`candidate_summary` artifact. `/api/jobs/JOB_ID/review` and
`/v1/jobs/JOB_ID/review` convert that artifact into API-first
`review.candidates` records with candidate IDs, boxes, scores, review status,
warnings, rejection reasons, artifact preview IDs when available, and an
aggregate `candidateSummary`. UI code should render these API records instead
of fabricating final candidates or tracks.

The Local UI's default goal is `auto_object_proposals` with the Clean preset.
Balanced and Maximum Recall are explicit preset choices in the run config, and
Trace Everything is kept behind an expert disclosure with cost/noise
acknowledgement. The candidate browser uses API-returned thumbnails, mask
previews, scores, rejection reasons, and review status; synthetic tracks are
only used as non-exportable in-flight demos before API results exist.

Selected-candidate tracking is API-owned. `POST /api/jobs/JOB_ID/track-selected`
or `POST /v1/jobs/JOB_ID/track-selected` validates selected candidate IDs
against `candidates.json`, tracks only those candidate masks, and writes updated
tracks/scene artifacts. With `exportReviewRequired`, generated tracks are
`review_pending` so auto-discovered objects cannot be exported without review.

## CLI Examples

CPU moving-region discovery:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/motion_discovery \
  --discovery-provider motion_foreground \
  --discovery-min-area 20 \
  --discovery-max-candidates 3 \
  --max-frames 12
```

The same workflow is available in the local UI through `Find moving objects`.
It uses the CPU `motion_foreground` discovery provider, records threshold and
morphology settings in `candidates.json`, writes generated foreground masks
under `discovery/motion_foreground/`, and carries each candidate score into
track confidence for review.

External mask discovery from a manifest:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/external_discovery \
  --discovery-provider external_masks \
  --discovery-config '{"objects":[{"object_id":"ball","label":"Red ball","mask_dir":"masks/ball"}]}'
```

Text detector mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/text_mock \
  --discovery-provider text_detector \
  --discovery-text "red ball . hand" \
  --discovery-config '{"mock":true}' \
  --max-frames 2
```

Local UI text-discovery smoke path:

1. Launch `python3 -m motionjson.cli ui --no-open --mock`.
2. Register a source video and choose `Find objects from text`.
3. Start a mock job. The worker runs `text_detector` mock discovery, writes
   `candidates.json`, adapts candidate mask sequences into object specs, and
   writes `tracks.json`.
4. Review the Candidates and Tracks panels before export. If real detector
   dependencies or weights are missing, diagnostics still report that status;
   mock mode does not imply that open-vocabulary detection is installed.

Known-class preset mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/class_mock \
  --discovery-provider class_detector \
  --discovery-class-preset vehicles \
  --discovery-class forklift \
  --discovery-config '{"mock":true,"confidence_threshold":0.4}' \
  --discovery-max-candidates 3 \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

The local UI `Find known classes` preset uses the same mock path in no-model
mode. The selected preset is recorded as `discovery.config.class_preset`,
custom labels are recorded as `discovery.config.classes`, and
`confidence_threshold` is kept in `candidates.json` metadata so users can see
the detector settings that would apply once a real known-class backend is
configured.

Automatic mask proposal mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/auto_masks_mock \
  --discovery-provider sam_auto_masks \
  --discovery-config '{"mock":true,"keyframes":[0],"max_candidates":3}' \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

In the local UI, `Propose all visible segments` uses the same mock path when
started from `--mock`: keyframe settings and proposal filters are recorded in
`candidates.json`, generated masks feed the shared tracker, and
`tracks.json` carries filter/dedupe summaries for review.

SAM3 concept mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_concept_mock \
  --discovery-provider sam3_concept \
  --discovery-config '{"mock":true,"concept":"red ball . hand"}' \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

SAM3 exemplar mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_exemplar_mock \
  --discovery-provider sam3_exemplar \
  --discovery-config '{"mock":true,"exemplars":["crop_001","crop_002"]}' \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

SAM3 auto-mask mock smoke check:

```bash
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_auto_mock \
  --discovery-provider sam3_auto_masks \
  --discovery-config '{"mock":true,"qualityPreset":"clean"}' \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

Local SAM3 concept run, only after diagnostics report `sam3-local` ready:

```bash
SAM3_LOCAL_MODEL=/path/to/sam3-model \
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_concept \
  --discovery-provider sam3_concept \
  --discovery-config '{"concept":"red ball","useVideoSession":true}' \
  --mask-provider mock \
  --max-frames 24 \
  --min-area 1
```

Hosted SAM3 concept smoke run, only after endpoint/auth are configured and the
user accepts provider cost/privacy terms:

```bash
SAM3_HOSTED_URL=https://provider.example.test/sam3 \
SAM3_HOSTED_API_KEY=... \
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam3_hosted_concept \
  --discovery-provider sam3_concept \
  --discovery-config '{"providerPreference":"sam3-hosted","concept":"red ball","allowNetwork":true,"acknowledgeCostPrivacy":true}' \
  --mask-provider mock \
  --max-frames 2 \
  --min-area 1
```

Local SAM2 automatic proposal run:

```bash
SAM2_LOCAL_CHECKPOINT=/path/to/sam2.pt \
SAM2_LOCAL_CONFIG=/path/to/sam2.yaml \
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/sam2_auto_objects \
  --discovery-provider auto_object_proposals \
  --discovery-config '{"providerPreference":"sam2-local","qualityPreset":"clean"}' \
  --mask-provider mock \
  --max-frames 12 \
  --min-area 1
```

The SAM2 adapter samples keyframes according to the selected preset, calls
SAM2 automatic mask generation, filters by area/stability/duplicate overlap,
writes accepted and rejected candidate artifacts, and uses SAM2 video
propagation for accepted candidate mask sequences when the local predictor is
available. If propagation is not exposed by an injected test backend, the
candidate warning explains that selected tracking will use the keyframe seed
mask sequence. Missing `sam2`, `torch`, checkpoint, config, or device support
is surfaced in diagnostics and job failure logs; MotionJSON does not silently
fall back to pretending SAM2 ran.

API-first clean object proposal config:

```json
{
  "discovery": {
    "mode": "auto_object_proposals",
    "config": {
      "qualityPreset": "clean"
    }
  }
}
```

Maximum recall is explicit and remains review-gated:

```json
{
  "discovery": {
    "mode": "auto_object_proposals",
    "config": {
      "qualityPreset": "maximum_recall"
    }
  }
}
```

Trace Everything is expert/experimental and must acknowledge cost/noise before
the typed config validates. It stays capped, writes rejected candidates for
review, and marks generated tracks as review-pending so export workflows block
until a user reviews the result:

```json
{
  "discovery": {
    "mode": "auto_object_proposals",
    "config": {
      "qualityPreset": "trace_everything",
      "costWarningAcknowledged": true
    }
  }
}
```

## Candidate Shape

`candidates.json` records:

- `id`, `label`, `source`, `frameIndex`, `zIndex`;
- optional `point`, `box`, `maskRef`, and `score`;
- provider metadata including UI descriptions, filter settings, and `maskDir`
  when the candidate can feed the current mask-tracking pipeline directly.

Candidates with `metadata.maskDir` are adapted into `ObjectExtractionSpec`
values backed by `ExternalMaskProvider`, then processed by the shared
tracking/vectorization/export path.

Accepted candidates also become first-class MotionJSON object metadata. The
exporter writes a `discovery` block onto scene objects/layers, object manifests,
object motion files, web manifests, and track metadata. That block carries the
candidate ID, source/provider/model, preset, scores, review status, selected or
ignored state, track confidence, motion coverage, artifact references,
rights/source lineage, and optional correction-history reference. Runtime and
SDK clients can read this block directly and ignore future additive fields.

## Capability Behavior

Run diagnostics before presenting discovery choices:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

`manual_prompt`, `motion_foreground`, and `external_masks` are no-model local
providers when base dependencies are installed. `auto_object_proposals` and
`sam_auto_masks` report runnable only when the optional SAM2 automatic mask
generator, torch, checkpoint, and model config are present; otherwise they
report `missing_dependency`, `missing_model`, or `not_configured`. `sam3_concept`,
`sam3_exemplar`, and `sam3_auto_masks` expose mock modes for UI/API testing.
Real local SAM3 execution uses the optional local adapter and reports missing
SAM3 package, Python/CUDA runtime, or model setup instead of falling back
silently. Hosted SAM3 remains network-required, provider-billed, and blocked
until the request explicitly includes `allowNetwork` and
`acknowledgeCostPrivacy`. `text_detector` and `class_detector` remain
scaffolded until detector adapters are wired. Those warnings do not break the
base CLI, and mock mode remains available for local smoke checks.
