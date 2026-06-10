# Local UI

This page documents the current Local UI behavior. It is not a requirement to
preserve current cards, right rails, steppers, dashboards, or panel layout
during a full redesign. For redesign work, use
`docs/product/ui_redesign_brief.md` plus the safety invariants.

The dependency-light local UI lets you inspect MotionJSON provider readiness,
create local projects, register source videos, draw prompts, start jobs, review
tracks, correct extraction results, export validated MotionJSON, and save
reusable motion layers. It runs against the existing SQLite backend and
filesystem storage. The normal workflow is first-run-user-first: choose a goal,
add a video, use Model setup to install/check/cache the recommended model
through server-owned setup jobs, run extraction, recover from failures, review,
and export. Debug mock mode remains available only for contributor smoke
checks.

## Commercial Workspace Mode

The sidebar Workspace panel collects the product-level state a nontechnical
user needs before running extraction:

- recent projects, source videos, and jobs;
- guided tasks such as tracing one object, text-guided discovery, moving
  objects, and reviewing an existing result;
- saved local preferences for default goal, default mask provider, default
  export preset, and last project;
- provider-settings summary that highlights SAM local/hosted readiness;
- export preset inventory.

The backing API routes are:

- `GET /api/health`
- `GET /api/deployment-readiness`
- `GET /api/workspace`
- `GET /api/preferences`
- `POST /api/preferences`
- `GET /api/commercial-readiness`

Preferences are local SQLite rows for the reserved local UI user. They do not
store provider secrets, media paths, or cloud account data. Hosted provider
keys stay in the Provider settings flow and remain redacted.

The Commercial readiness panel is intentionally a foundation, not billing. It
shows local account/team placeholders, usage and cost policy, provider run
history, export history, privacy notices, and rights reminders so commercial
review work has an audit trail before team accounts or paid plans exist.

Deployment readiness is explicit and conservative. Normal local runs report
`mode: "local_single_user"` with SQLite, local file storage, server-owned
provider settings, a SQLite-backed model-run store, and an in-process worker.
`MOTIONJSON_DEPLOYMENT_PROFILE=hosted_single_tenant` or
`hosted_multi_tenant` requests a hosted profile, but hosted readiness remains
blocked until real hosted auth, database, object storage, external queue,
secrets management, worker isolation, team boundaries, and billing are
implemented and configured. In those hosted profiles, private Local UI API
routes return 401 instead of falling back to the local single-user account.

## Guided First Run

The default Local UI opens in one visible guided workflow:

1. `Start`
2. `Video`
3. `Model setup`
4. `Prepare & run`
5. `Run`
6. `Review & export`

`Start` begins with a goal-first chooser for nontechnical users. The main
canvas offers plain-language choices:

- Cut out one object.
- Pick objects from one frame.
- Find by description.
- Review previous result.

`Find everything in scene` remains available under Advanced tasks for cases
where the user needs a broader scene sweep instead of the faster one-frame
pick flow.

When a local video is registered, MotionJSON inspects the source codec. If the
source is already browser-safe, the player uses the source asset directly. If
the source is not browser-safe, MotionJSON prepares a local browser-safe H.264
preview automatically when FFmpeg is available and generates a poster image for
Setup. The normal product flow blocks `Prepare` and `Review` until that browser
preview is usable.

The Run preview panel shows a readable plan by default: goal, source status,
model/provider mode, prompt needs, review gate, and next steps. The generated
`ExtractionRunConfig` JSON remains available under Advanced for CLI and
developer users, but it is no longer the default explanation of what will run.

## Guided Workspace Flow

The Local UI uses a progressive workflow instead of showing every setup,
diagnostic, review, correction, and export card at once. The main product flow
guides users through:

1. Start.
2. Video.
3. Model setup.
4. Prepare and run.
5. Run monitor.
6. Review and export.

Guided mode now keeps one visible footer action per screen. The footer always
shows `Back` plus one explicit primary action such as `Choose video file`, `Continue`,
`Run trace`, `Run search`, `Run motion scan`, or `Export reviewed objects`.
Secondary actions such as demo video, setup state details, `Change model`, or
review bulk actions stay visually secondary inside the current panel.

The default object-discovery path is now `Pick objects from one frame`. It
uses the current preview frame as the first review pass, then pauses for a real
selection step before any full-video tracking begins. The flow is: choose a
frame, run a one-frame scan, keep and rename the objects you want, then start
a child tracking job for those selected objects only.

The Video step supports direct local upload. Choosing a video file creates the
local project when needed, stores the source in the local asset library, and
prepares the browser preview from that registered source. The advanced local
path form remains available for CLI-style workflows or environments where the
browser file picker cannot access the source file.

After a run starts, the Job Center becomes part of the main workspace instead
of living only in the details rail. It shows the selected job, active/recent
jobs, normalized status, progress, provider, live mask/cutout previews,
artifacts, and cancel state. Failed runs switch the main screen to Run
monitor and surface logs plus fallback diagnostics without requiring an extra
discovery step.

The review sequence is explicit: `Candidates` -> `Track selected` -> `Tracks`
-> `Corrections` -> `Export`. If a run has candidates but no tracks, the
primary action is `Track selected`. If tracks exist but none are marked for
export, the primary action is `Mark reviewed`. A ready reviewed result uses
`Export reviewed objects`. Failed or canceled jobs keep the primary action on
diagnostics/log recovery rather than showing an empty review surface.

Candidate review, selected-track diagnostics, relabel controls, correction
history, and export gating now live in the same main review surface instead of
being split across the right rail.

Local project creation is no longer a required early decision in guided mode.
When a user adds a video, starts from the bundled demo, or opens an existing
MotionJSON result, the Local UI creates a starter local project automatically
if one does not already exist. Manual project switching and manual project
creation remain available under `Project options`. Advanced tracing goals are
visible on the Start screen as compact rows; they no longer require an
all-panels dashboard.

The left navigation can collapse to a compact rail with the active goal and a
Menu button. Run monitor, review, corrections, export, logs, artifacts, and
model setup support are folded into the main workflow panels instead of a
right details rail. The workflow stepper supports ArrowRight, ArrowDown,
ArrowLeft, ArrowUp, Home, and End for keyboard navigation.

Diagnostics are quieter on successful runs but are not hidden when they matter.
Provider warnings stay visible before a run, failed runs open logs, and
fallback/raster/vector-unavailable diagnostics open automatically in the Run
monitor or review step.

## Model Setup

The main workspace includes a nontechnical Model setup panel before the
extraction controls. It recommends exactly one compatible path by default and
hides alternatives behind `Change model`:

- Cut out one object: `sam2-local` prompt tracking when checkpoint/config paths
  are ready, otherwise hosted SAM2 if explicitly selected.
- Pick objects from one frame: the same recommended path as scene sweep, but
  optimized for one fast proposal pass before selected tracking.
- Find everything in scene: `sam3-local` Scene Sweep first. The scene-sweep
  runtime uses `sam3TrackerModel=facebook/sam3` by default or a local Hugging
  Face `from_pretrained` directory. It must not receive a single `sam3.pt`
  checkpoint path. `SAM2 HF automatic masks` is the fallback and uses
  `facebook/sam2.1-hiera-large` without requiring the official `sam2` package.
- Find by description: SAM3 concept/text providers. A prompt is required.
- Review previous result: no model setup is required.

Normal mode shows the setup state and one primary action. For local SAM setup,
the normal path is `Prepare local model`, then `Run smoke test` when a cached
model still needs verification, then `Continue to run` when setup is complete.
Raw environment variables, local paths, custom endpoints, manual commands,
logs, diagnostics, and JSON stay behind `Advanced`. The setup state machine is:
`not_configured`, `checking_environment`, `needs_access`,
`needs_download_confirmation`, `caching_model`, `installing_runtime`,
`preparing_model`, `smoke_testing`, `ready`, and `failed_recoverable`.

Local SAM2 HF and SAM3 Scene Sweep setup also includes a server-side
`modelCache` state. MotionJSON treats a model as runnable only when the runtime
is available and the selected Hugging Face repo or local `from_pretrained`
directory is already resolved locally. Cache state is derived from saved setup,
local model directories, previous setup jobs, and Hugging Face cache inspection
without exposing raw local paths in browser responses.

The capability report now includes a local environment profile and GPU-model
recommendation. CUDA environments are guided toward SAM3 Scene Sweep with
`facebook/sam3`; Apple MPS environments are told that SAM3 Scene Sweep remains a
CUDA-first workflow; CPU-only environments are guided to CPU-safe or explicitly
hosted paths. The recommendation is advisory only. Provider readiness, cached
model state, hosted opt-in, and smoke tests still decide whether a run can
start.

When Cache model completes, the backend records the resolved local
`from_pretrained` directory in provider settings for runtime use. Browser
responses show only that the path is known/recorded server-side and redact the
absolute path as `[LOCAL_PATH_REDACTED]`. Public cache state may include
`cached`, `serverPathRecorded`, `localPathDisplay`, and `runtimeModelSource`,
but raw `resolved_model_dir` stays backend-only.

For SAM3 Scene Sweep, `needs_access` is a normal UI step. The Model setup panel
asks for a Hugging Face token in the main flow, saves it locally as a redacted
secret, and uses it only for allowlisted `check_access` and `cache_model` jobs.
Users do not need to pre-set `HF_TOKEN` before launching the UI.

The form saves local model paths, selected profile/model, optional endpoint,
API key replacement, and hosted cost/privacy opt-in through
`/api/provider-settings`; browser responses never echo raw keys or raw local
absolute paths. Setup actions run through allowlisted server jobs:

- `POST /api/provider-settings/{providerId}/setup/start`
- `GET /api/provider-settings/setup-jobs/{jobId}`
- `POST /api/provider-settings/setup-jobs/{jobId}/cancel`

Diagnose stays lightweight and offline. `prepare_model` is the guided local
setup action for SAM providers. It diagnoses runtime setup, blocks with the
next required user action when packages, access, or local paths are missing,
caches the selected model only after network/disk confirmation, records the
server-side path, and then runs a bounded smoke test after heavy-runtime
confirmation. Cache-model actions still exist for advanced/manual setup and
require explicit network/disk confirmation. The Local UI renders setup
confirmations in-page instead of using native browser confirmation dialogs, so
Colab/proxied browser sessions can inspect the pending action, provider, model,
network, disk, heavy-runtime, and cancel state. Hosted smoke tests require
`allowNetwork`, `allowHosted`, and `acknowledgeCostPrivacy`; local SAM smoke
tests require `allowHeavyLocal` before importing heavy model runtimes.

The guided workflow derives run config from a normalized connection contract:
connection ID, provider ID, engine, display label, hosted profile, locality,
capability flags, readiness, and hosted-call opt-in remain separate. Display
labels such as `Roboflow SAM3` are user-facing only; policy and validation use
provider IDs and connection IDs.

## Run Logs And Setup Logs

The Run monitor shows a process overview before the raw event list: current
phase, provider, progress, stale-progress warning, and the next recovery action
when one is known. Each event keeps the backend message visible, then expands
with stage/provider/model/reason chips, progress bars, suggested fixes, and
debug metadata. The event list now uses a terminal-style surface, and the main
Run monitor shows the latest candidate previews, masks, and cutouts that have
already been registered for the selected run. Failures, raster fallback,
whole-frame masks, CUDA/model/cache problems, and provider errors are
visually promoted instead of being hidden in raw JSON.

Partial object recovery is part of the review contract. During multi-object
SAM runs, the worker checkpoints each completed object before the final global
export. If a later object fails, the backend can synthesize the root review
payload from those checkpoints so completed objects remain inspectable. The
`/api/jobs/JOB_ID/review` response then includes:

- `partialSuccess: true`
- `partialReview`: redacted diagnostic details, failed object/frame when known,
  and captured runtime proof when available
- `reviewableObjectCount`: number of completed objects recovered for review

Recovered objects are review-required and are not automatically marked for
export. The UI should show the completed objects in Review, show the failed
object/frame as a diagnostic row, and keep export blocked until the user
explicitly keeps and includes at least one recovered track.

Runtime proof is also a job-level contract. For SAM jobs, the extraction worker
records an environment proof before model work starts, including
`acceleratorKind`, `runtimeProofStatus`, requested/actual device,
CUDA/MPS availability, and memory snapshot fields when available. A status of
`environment_verified` means the worker process can see the accelerator, but it
does not yet prove the model loaded there. When the SAM3 scene-sweep subprocess
loads the model, it emits a stronger `runtimeProofStatus: verified` proof with
`loadedOnCuda` or `loadedOnMps`. The UI may show `CUDA available` for the first
case and `CUDA active` only after model placement is verified.

Model setup jobs use the same event renderer. Install, access-check, cache, and
smoke-test logs remain visible with progress, cancellation, blocked state, and
redacted debug metadata, so users can see whether setup is installing runtime
packages, checking Hugging Face access, downloading/resolving weights, verifying
the cache, or recording the resolved model path.

## Automatic Labels

MotionJSON now attempts a small local image-classification pass when a new
object still has a generic placeholder label such as `selected_object` or
`Candidate 2`. The current implementation uses the optional
`classifier` extra (`torch` + `torchvision`) and
`torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1`.
It only replaces placeholder names with a short user-facing object label when
the prediction is confident enough and maps cleanly to a supported friendly
class such as `Ball`, `Cup`, `Bottle`, `Phone`, `Plant`, `Car`, `Dog`, or
`Cat`. User-entered labels still win, and duplicate automatic labels are
numbered (`Ball 2`, `Ball 3`) for review clarity.

## Model Planning Connector Contract

The Local UI exposes a server-side model planning contract for future
model-assisted workflows. `fake-local-planner` is the default deterministic
no-network connector for tests and smoke runs. `openrouter-planner` is a
settings-backed hosted planning surface that reads the existing OpenRouter
provider settings and remains non-runnable until an OpenRouter transport is
implemented. UI-MODEL-04 adds `openai-planner`, a server-side OpenAI Responses
API connector for generating reviewable run plans from text intent.

`openai-planner` never runs by default. It requires all of the following before
any hosted request is attempted: server-side OpenAI provider settings or
environment credentials, hosted-call opt-in in provider settings, and a
per-request payload with `allowNetwork: true` plus
`acknowledgeCostPrivacy: true`. The connector sends only text intent and
redacted project context. It does not send video frames, local absolute paths,
storage keys, or browser-supplied API keys.

OpenAI and OpenRouter connector readiness use the existing Provider settings
precedence: environment credentials override local SQLite secrets, local saved
model choices override defaults, and `OPENAI_DEFAULT_MODEL` or
`OPENROUTER_DEFAULT_MODEL` supplies the effective model when no local model is
selected. Raw keys remain server-side and are never returned by
`/api/model-providers`.

The model connector routes are:

- `GET /api/model-providers`
- `GET /api/model-providers/PROVIDER_ID`
- `POST /api/model-providers/PROVIDER_ID/test`
- `POST /api/model-providers/PROVIDER_ID/estimate`
- `POST /api/model-runs`
- `GET /api/model-runs/RUN_ID`
- `GET /api/model-runs/RUN_ID/events`
- `POST /api/model-runs/RUN_ID/cancel`
- `POST /api/jobs/JOB_ID/model-plan`

Model runs are process-local and volatile in this phase. They exist to validate
the API contract and event shapes, not to persist model state across restarts.
Attaching a model plan to an extraction job records a redacted
`model_plan_attached` job event and does not enqueue extraction. Extraction
still starts only through the existing job confirmation path.

The fake connector returns a proposed `ExtractionRunConfig`, validation result,
privacy summary, zero-local cost estimate, and `requiresUserConfirmation: true`
only when the UI is running in explicit debug mode. The OpenAI connector treats
model output as an untrusted proposal: MotionJSON coerces it into explicit CV
providers, generates the `ExtractionRunConfig` locally, validates it, and still
marks the plan as requiring user confirmation. Segmentation and tracking in the
normal UI are routed through configured SAM2/SAM3, hosted SAM profiles,
`threshold`, `motion`, `external`, or detector discovery modes; OpenAI does not
segment video. All public model responses pass through the Local UI sanitizer
so API keys, bearer tokens, local absolute paths, storage keys, and `file://`
URIs are not returned to browser code.

## Launch

Use the packaged console command for normal local UI sessions:

```bash
motionjson ui
```

Use the module entry point for non-opening local sessions:

```bash
python3 -m motionjson.cli ui --no-open
```

By default the UI uses:

- database: `.motionjson/backend.sqlite`
- storage root: `.motionjson/storage`
- host: `127.0.0.1`
- port: `8766`

Override those paths for tests or demos:

```bash
python3 -m motionjson.cli ui \
  --db /tmp/motionjson-local-ui/backend.sqlite \
  --storage-root /tmp/motionjson-local-ui/storage \
  --host 127.0.0.1 \
  --port 8766 \
  --no-open
```

Contributor-only debug smoke checks use `--debug-mock`. The hidden `--mock`
alias is deprecated and prints a warning. Debug mock mode does not pretend
SAM2, CUDA, detectors, FFmpeg, or model weights are available; those statuses
still come from provider diagnostics.

On Windows PowerShell, use the module entry point after activating the virtual
environment:

```powershell
python -m motionjson.cli ui --no-open
```

The sidebar First Run checklist summarizes base dependency readiness, SAM
provider setup, optional model extras, and FFmpeg status from
`/api/capabilities`. It keeps optional SAM2, SAM3, detector, hosted, and FFmpeg
setup clearly marked as diagnostics instead of claiming unavailable providers
are ready.

The local UI worker starts `sam2-local`, `sam2-hf-auto-masks`, `sam2-hosted`,
`sam3-local`, `sam3-hosted`, `threshold`, `motion`, and `external` extraction
jobs.
Discovery-owned SAM3 runs still route through the same review/filter/link/export
path, but the saved run config now records the selected SAM3 engine directly in
`provider.name` plus `provider.sam3` instead of hiding it behind a threshold
placeholder. `motion_foreground` is CPU/no-model and runs from the
`Find moving things` preset.

## Routes

The UI serves static files under `/ui/` and local JSON routes under `/api/`:

- `GET /api/health`
- `GET /api/capabilities`
- `GET /api/provider-settings`
- `POST /api/provider-settings`
- `DELETE /api/provider-settings/PROVIDER_ID`
- `POST /api/provider-settings/PROVIDER_ID/test`
- `POST /api/provider-settings/PROVIDER_ID/diagnose`
- `POST /api/provider-settings/PROVIDER_ID/smoke-test`
- `POST /api/provider-settings/PROVIDER_ID/setup/start`
- `GET /api/provider-settings/setup-jobs/JOB_ID`
- `POST /api/provider-settings/setup-jobs/JOB_ID/cancel`
- `GET /api/run-config/defaults`
- `POST /api/run-config/validate`
- `GET /api/exports/formats`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/videos?projectId=PROJECT_ID`
- `POST /api/videos`
- `GET /api/videos/VIDEO_ID/content`
- `POST /api/videos/VIDEO_ID/prepare-browser-preview`
- `GET /api/assets/ASSET_ID/content`
- `GET /api/jobs?projectId=PROJECT_ID`
- `POST /api/jobs`
- `GET /api/progress?projectId=PROJECT_ID`
- `GET /api/jobs/JOB_ID`
- `GET /api/jobs/JOB_ID/events`
- `GET /api/jobs/JOB_ID/artifacts`
- `GET /api/jobs/JOB_ID/review`
- `GET /api/jobs/JOB_ID/corrections`
- `POST /api/jobs/JOB_ID/track-edits`
- `POST /api/jobs/JOB_ID/track-selected`
- `POST /api/jobs/JOB_ID/cancel`
- `POST /api/jobs/JOB_ID/validate`
- `POST /api/jobs/JOB_ID/exports`
- `GET /api/artifacts?jobId=JOB_ID`
- `POST /api/projects/PROJECT_ID/library-assets`
- `GET /api/library/assets`
- `GET /api/library/assets/LIBRARY_ASSET_ID`
- `POST /api/library/collections`
- `GET /api/library/collections`
- `POST /api/library/collections/COLLECTION_ID/assets`
- `GET /api/library/collections/COLLECTION_ID/assets`
- `POST /api/library/packs`
- `GET /api/library/packs`
- `POST /api/projects/PROJECT_ID/imports/motionjson`

The local UI creates a reserved local user in the selected SQLite database and
uses that user for project, video, and job queries. API responses omit internal
storage keys, local `file://` storage URIs, and token material. Registered
videos expose a `browserPreview` block that includes preview status, codec,
dimensions, duration, and local content URLs for the chosen preview video and
poster image. Source video bytes still come from `/api/videos/VIDEO_ID/content`
without exposing the storage path, while browser-preview derivatives and poster
images are served through `/api/assets/ASSET_ID/content`.
JSON, static shell, video, and artifact responses use local no-store headers.
The frontend only opens generated content links that point back to local
`/api/videos/.../content` or `/api/artifacts/.../content` routes.

## Job Lifecycle Summaries

Job responses preserve their existing public fields and add a normalized
`lifecycle` block for UI flow state. The block is available on jobs returned by
`GET /api/jobs?projectId=...`, `GET /api/jobs/JOB_ID`, and
`GET /api/progress?projectId=...`.

`lifecycle` includes:

- normalized job status: `queued`, `running`, `waiting_review`, `succeeded`,
  `failed`, or `canceled`;
- phase: `queued`, `validating`, `extracting`, `discovering`, `tracking`,
  `writing_artifacts`, `review_ready`, `exporting`, `complete`, or `failed`;
- progress with `known`, `percent`, and a short label. When progress is inferred
  instead of event-measured, `known` is `false`;
- provider summary with separate connection ID, provider ID, display label,
  engine, locality, and hosted-call opt-in state;
- latest event summary;
- failure headline, reason code, detailed message, and suggested recovery action;
- review counts for candidates, selected candidates, tracks, exportable tracks,
  diagnostics, and raster/vector-unavailable state;
- action gates for cancel, retry, review, track selected, and export;
- a single next-action label and reason.

`GET /api/workspace` and `GET /api/progress?projectId=...` also include a
`jobCenter` block:

```json
{
  "format": "motionjson.local_ui_job_center.v0.1",
  "activeJobsCount": 1,
  "selectedJobId": "job_id",
  "activeJobs": [],
  "recentJobs": []
}
```

This contract is provider-neutral. SAM2 and SAM3 labels are display values only;
policy logic should use provider IDs, connection IDs, engine, locality, and
readiness fields instead of comparing labels.

## Candidate Review Payloads

`GET /api/jobs/JOB_ID/review` is the source of truth for object candidates.
When a job writes `candidates.json`, the review payload includes
`review.candidates` with normalized API records:

- `candidateId`, `objectId`, `label`, `source`, `providerName`, and
  `frameIndex`;
- optional `thumbnailArtifactId` and `maskPreviewArtifactId`;
- `box`, `areaRatio`, `stabilityScore`, `motionScore`, `confidence`, and
  `frameCoverageEstimate`;
- `warnings`, `rejectionReason`, `defaultSelected`, and `reviewStatus`.

The same response includes `review.candidateSummary` with aggregate counts:
`candidateCount`, accepted/rejected/default-selected counts, rejection reason
counts, `qualityPreset`, `providerName`, and `requiresReview`. The older
`candidateSummary.provider`, `candidateSummary.config`,
`candidateSummary.video`, and `candidateSummary.candidates` fields remain for
current UI compatibility, but new UI code should render `review.candidates`
and the aggregate summary instead of inventing candidate or track state.
Mock `auto_object_proposals` jobs write deterministic thumbnails and mask
preview overlays under `discovery/`; once those files are registered as
artifacts, the review route resolves their relative paths into
`thumbnailArtifactId` and `maskPreviewArtifactId`.

The right-rail candidate browser renders `review.candidates` from this API
payload. It supports Clean, Balanced, and Maximum Recall run presets, filters
for selected/stable/moving/non-background/non-duplicate candidates, a minimum
coverage threshold, and a Track selected action that posts selected candidate
IDs back to the backend. The Trace Everything control is isolated in an
advanced disclosure and requires explicit acknowledgement before its config can
validate. Trace Everything output is intentionally review-pending and blocked
from export until the user reviews selected objects.

Guided run config also carries `discovery.config.adaptiveParameters` when the
UI auto-tunes scene sweep settings. This block records the requested effort,
resolved values, source labels such as `auto` or `user_override`, prior failure
reason, materialization risk, workload risk, video dimensions, duration, source
FPS/frame count when ffprobe can read them, coverage status, and chip
explanations. Debug reports include the same block so a run can show, for
example, `effortPreset: high_quality` while also explaining that sample FPS,
frame count, object count, or SAM3 batch size were reduced after
`worker_heartbeat_stale` or another asset-prep failure.

Auto tuning is now coverage-first for SAM3 Scene Sweep. The UI estimates the
frames needed to cover the whole clip at the selected effort, then sets
`sampleFps` and `maxFrames` together. Short high-quality clips can therefore
increase `maxFrames` above the old fixed preset cap instead of sampling only the
front of the video. Long or high-resolution clips may lower sampling density so
the run still spans the full video; the chip labels this as `Full clip, lower
density` or `Sparse full clip` instead of presenting it as uncompromised high
quality. User overrides remain explicit and are recorded in the same metadata
block.

SAM3 Scene Sweep run logs now include inner operation events in addition to the
outer `candidate_discovery` phase. Debug reports include an **In-flight
Diagnostics** section with the last operation, candidate/object, record number,
frame/keyframe, subprocess liveness, optional GPU probe, and stack-probe status
when available. Logs should identify the last in-flight operation with event
metadata such as
`scene_sweep_generator_call_started`, `sam3_inference_started`,
`sam3_postprocess_started`, `sam3_candidate_tracking_started`, or
`sam3_candidate_preview_started`. If the isolated worker waits or times out,
the parent event includes `lastChildEvent` and `currentOperation` so the report
distinguishes model inference, postprocessing, candidate tracking, mask
encoding/file writes, GPU visibility, Python stack location, and IPC waits.

The browser cards show thumbnails and mask previews when the API resolves them
to local artifact links. When previews are missing, the card keeps the same
space and labels the empty thumbnail/mask slots instead of collapsing the
layout. Candidate status chips use plain review language: selected, rejected,
background-like, duplicate, low confidence, needs review, and reviewed for
export. The candidate panel also renders retry suggestions that point users to
Maximum Recall, smaller max-area settings, the moving-object workflow, extra
prompts, or mask import when the candidate mix indicates those recovery paths.

The review response also includes `review.timeline` in
`motionjson.review_timeline.v0.1` format. This API-owned summary contains
candidate appearance markers, track start/end/loss markers, marker counts, and
suggested keyframes derived from configured discovery keyframes or review
markers. The preview timeline renders those API markers and lets users reuse
suggested keyframes in the next discovery config; local keyframes are shown as
config input, not fabricated review output.

`POST /api/jobs/JOB_ID/track-selected` accepts `candidateIds`,
`trackMode: "selected_only"`, and `exportReviewRequired`. The backend validates
that each ID belongs to the job's candidate artifact, rejects ignored/rejected
candidates, runs tracking for the selected mask candidates only, and returns
updated `artifacts` plus `review`. When `exportReviewRequired` is true, selected
tracks are marked `review_pending` and export validation blocks until review
state explicitly includes them.

## Provider And Model Settings

The right inspector includes a Provider settings panel for choosing providers,
models, local model paths, and optional credentials without editing shell
profiles. Local providers such as `sam2-local`, `sam3-local`, `threshold`,
`motion`, and `external` do not accept API keys. Hosted providers show a cost
and privacy warning before they can be marked as allowed for hosted calls.

The Local UI currently exposes settings for:

- `threshold`, `motion`, and `external`: local/free, no key required.
- `sam2-local`: local SAM2 model selection and diagnostics. Model weights and
  package setup come from saved local paths or `SAM2_LOCAL_CHECKPOINT` and
  `SAM2_LOCAL_CONFIG`.
- `sam2-hosted`: hosted profile, model, API key, optional endpoint, and
  explicit hosted-call opt-in. The built-in Replicate SAM2 video profile uses
  `REPLICATE_API_TOKEN`; custom endpoints use `HOSTED_SEGMENTATION_URL` and
  `HOSTED_SEGMENTATION_API_KEY`.
- `sam3-hosted`: hosted profile, model, API key, optional endpoint, and
  explicit hosted-call opt-in for text concept discovery. Built-in profiles
  cover Roboflow SAM3 concept segmentation and Fal SAM3 image, plus a custom
  SAM3-compatible endpoint.
- `sam3-local`: SAM3 Scene Sweep setup through `sam3TrackerModel` /
  `facebook/sam3`, plus advanced official-package SAM3 `sam3.pt` checkpoint
  setup through `sam3ModelPath` / `SAM3_LOCAL_MODEL`. The normal Scene Sweep
  cache path is recorded server-side after `Prepare local model` or `Cache
  model`; do not paste it into `sam3ModelPath`. Use `sam3ModelPath` only for
  advanced concept/exemplar workflows that require a real local `sam3.pt`
  checkpoint.
- `openai`: OpenAI model selection and API key for hosted plan generation. It
  is not a mask or segmentation provider.
- `openrouter`: LLM/VLM model selection and API key for reasoning only. It is
  not a mask or segmentation provider.
- `text_detector` and `class_detector`: local model settings for scaffolded
  detector surfaces. They remain capability-gated until concrete dependencies
  and adapters are configured.

Provider settings are stored in the selected local SQLite database for the
reserved Local UI user. Raw keys are never returned by `/api/provider-settings`,
`/api/capabilities`, validation responses, screenshots, or error messages.
Environment variables take precedence over local UI settings for headless/CLI
work. Saved hosted keys feed server-side model connector readiness and tests;
the OpenAI planning connector still requires explicit per-run hosted
confirmation, and the local extraction worker reports missing SAM/CUDA/model
dependencies instead of falling back to debug mocks.
See [Provider API keys](security/api_keys.md) for storage, redaction, deletion,
and hosted-provider guidance.

## Product Shell

The commercial Local UI shell is organized around a stable app frame:

- collapsible left navigation for tracing goals, workspace, first-run
  readiness, local API, and capabilities;
- guided main workspace with a stepper, prior-step summaries, video/prompt
  preview when relevant, inline advanced tasks, run monitor, review,
  corrections, export, asset library, logs, and artifacts;
- route diagnostics remain debug-only and are not required for the normal
  workflow.

The default visible workflow is: choose a goal, add or select a video, connect
one compatible model when needed, prepare the run, then review and export.
Advanced
parameters, raw config JSON, raw routes, generated artifacts, library
management, logs, fallback diagnostics, and correction history remain available
through disclosure panels instead of being expanded by default.

Post-run work is grouped into a compact review sequence: candidates, track
selected, tracks, corrections, and export. The main review action follows that
sequence: track selected candidates before tracks exist, mark reviewed tracks
before export, and export only after reviewed objects are included. Clean runs
keep logs and generated artifacts collapsed. Failed runs and raster/vector
fallback states surface diagnostics immediately so users can see why object
tracks were not available.

Design and validation notes live in:

- [Local UI audit](design/local-ui-audit.md)
- [Local UI product principles](design/local-ui-product-principles.md)
- [Local UI design system](design/design-system.md)

The Asset Library panel wraps the existing local asset-library backend for
approachable reuse workflows. After a run or validated export registers
artifacts, select an artifact, save it as a `motion_sticker`, search saved
layers by text or tag, create a brand collection, add the selected saved layer
to that collection, and create a creator-approved pack. Pack creation uses the
backend rights gate: every included saved layer must already have approved
creator and commercial-use rights metadata. Rejected packs return a visible
local UI error instead of silently creating an unsafe pack. Library responses
keep `aiUsage: "none"` and omit storage keys and raw stored bytes.

`POST /api/run-config/validate` accepts either a run config object directly or
`{"runConfig": {...}}`. It returns `valid`, `errors`, `warnings`, and the
normalized `runConfig` when validation succeeds. Provider warnings are sourced
from capability diagnostics and job policy checks, so unavailable CUDA, SAM2,
detectors, FFmpeg-adjacent dependencies, or model weights remain visible before
a run is queued.

`POST /api/jobs/JOB_ID/track-edits` records deterministic local correction
events, applies artifact edits where possible, and updates review/export-
inclusion state for the job. Supported operations are `relabel`, `hide`,
`show`, `delete`, `merge`, `split`, `add_object`, and `repair`:

```json
{"operation": "relabel", "objectId": "object_0", "label": "Cue Ball"}
```

```json
{"operation": "merge", "keepObjectId": "object_0", "mergeObjectId": "object_1"}
```

`POST /api/jobs/JOB_ID/cancel` requests cooperative cancellation. Pending local
jobs move directly to `canceled`; running jobs move through
`cancel_requested` until the worker reaches a cancellation check. The selected
run panel exposes the same action through `Cancel run`.

Keyboard affordances are available in the prompt workspace: left/right arrows
step frames, shift plus left/right steps farther, Space plays or pauses the
preview, `M` marks a keyframe, `P` selects point prompts, `B` selects boxes, and
`E` selects the eraser. Text fields, selects, links, and buttons keep their
native keyboard behavior.

Preview overlays come from API review tracks when tracks exist. The scrubber
only shows a track inside its reported visible frame range, so a sparse or lost
track does not appear before its first marker or after its last marker. Timeline
marker clicks seek the video and select the related track for relabel,
hide/show, export inclusion, merge, split, add-object, or repair actions.

```json
{"operation": "split", "objectId": "object_0", "newObjectId": "object_0_tail", "frameRange": [24, 48]}
```

Corrections are stored in the local SQLite database and are returned from
`GET /api/jobs/JOB_ID/corrections` and the `correctionHistory` field on review
responses. Relabel, hide/show, delete, merge, and split update the editable
project review state used by local review and export-inclusion metadata.
After each track edit, the backend also writes
`review/review_state_manifest.json` as a `review_state_manifest` artifact. That
manifest records the correction history, current included/excluded track IDs,
track review summaries, raster fallback state, and `aiUsage: "none"` so a
review/export decision has a durable local audit trail.
`add_object` and `repair` are current no-model partial-rerun hooks: the
request is persisted with `aiUsage: "none"` and `partialRerun.available:
false` instead of silently pretending that SAM2, detectors, or other ML
providers ran. The correction UI surfaces these repair and partial-rerun
diagnostics in the saved edit message and correction history. It also shows a
track-specific correction guidance panel before the edit controls so users can
see whether the selected track exports, whether enough tracks are selected for
merge, and whether prompts are required before add-object or repair actions.

`POST /api/jobs/JOB_ID/validate` validates the corrected export state without
writing new artifacts. It accepts the same `preset`, `includeMasks`,
`includeContours`, and `includePreview` fields as the export route so the
preflight reflects the exact handoff settings. The response includes
`qualityRouting`, which explains the cached raster/vector/delivery/preview
route that export will use. MP4 preview validation is a dry run: it reports
`plan_ready` when FFmpeg is available and encodes only during final export.
The response also includes `objectLayerPack`, `exportValidationMessages`,
`rightsSummary`, and `exportWarnings` so selected-object handoff state,
unreviewed auto-discovery gates, source attribution, creator approval, license,
and commercial-use status are visible before handoff.
`POST /api/jobs/JOB_ID/exports` writes a validated MotionJSON handoff from the
corrected review state, registers the generated artifacts on the selected job,
and returns public content links for export files. The export panel now starts
with one-click handoff cards for the common destinations: website package,
reviewed MotionJSON scene, runtime snippet, Remotion plan, and developer
handoff bundle. Cards stay disabled with plain-language review/validation
reasons until a completed run has reviewed objects that are marked for export.
After export, the same cards become Open or Copy actions and the panel shows
copyable next steps that include the reviewed object IDs and runtime snippet.
Preset and mask/contour/preview switches remain available under Advanced
export settings for technical users.

The local UI supports these presets:

- `compact`: corrected `scene_graph.json`, final export manifest, validation
  report, `object_layer_pack.json`, `remotion_export_plan.json`,
  selected-object website package ZIP, and SVG overlay preview.
- `debug`: compact output plus contour/box JSON and copied cached mask PNGs.
- `vector-heavy`: corrected MotionJSON plus contour/box JSON for downstream
  vector tooling.
- `raster-fallback`: corrected MotionJSON plus mask and fallback-oriented
  diagnostics for runs where vector/object tracks need extra review.

Generated export JSON, ZIP assets, generated overlay previews, and ready MP4
previews are safe to open through `/api/artifacts/ARTIFACT_ID/content`; raw
extraction JSON and imported SVG files remain metadata-only unless they are
part of this explicit export workflow. Export manifests include source job id,
source asset id when known, preset, correction event count, included/excluded
object ids, sanitized run config/correction state, quality routing, validation
status, object-layer pack summary, export validation messages, rights warnings,
and `aiUsage: "none"`. Local absolute paths and storage keys are redacted from
public export payloads. The export panel and selected-track detail surface
rights status without requiring users to open raw JSON. The default export gate
is reviewed-selected-only: included rows come from tracks the user kept in
Review and marked for export, while rejected, hidden, pending, review-pending,
or unmaterialized correction tracks are summarized as not exported.

`POST /api/projects/PROJECT_ID/imports/motionjson` imports an existing
MotionJSON file or output directory into a succeeded `motionjson_import` job
for review. It validates the supplied path, copies the result into local
storage, and exposes the imported scene through the normal job review routes.

## Project And Video Flow

1. Open the UI command above.
2. Choose one of the normal goals from the first step: `Cut out one object`,
   `Find by description`, `Find everything in scene`, or
   `Review previous result`. Additional technical tasks live behind
   `Advanced`.
3. Add or select a source video. Guided mode creates a starter local project
   automatically the first time it needs one. MotionJSON prepares a browser-safe
   preview automatically before `Prepare & run` and `Review & export` open.
4. Use Model setup when the goal needs one. The UI shows one recommended path:
   SAM2 prompt tracking for point/box tracing, SAM3 Scene Sweep for
   everything-in-scene, SAM2 HF automatic masks as the fallback, and SAM3
   concept for text prompts. If SAM3 needs gated Hugging Face access, paste the
   token in this step. The primary `Prepare local model` button then runs the
   safe setup sequence and records any cached model path server-side, so users
   do not paste cached paths back into browser fields. Provider warnings stay
   visible before a run.
5. Add point, box, brush/erase mask, label, or keyframe prompts on the video
   overlay when the selected goal needs them. Prompt coordinates are native
   video pixels, not CSS canvas pixels.
6. Start extraction from the footer after the generated plan validates. The raw
   `ExtractionRunConfig` JSON remains available under `Advanced`.
   The optional advanced model plan panel can create a server-side planner
   config from the selected goal and plain-language intent; generated configs are
   revalidated before `Confirm and start` can create a job.
7. Review candidates first. Keep the candidates you want, then use `Track
   selected` to create object tracks.
8. Correct tracks if needed: relabel, hide/show, include/exclude from export,
   merge, split, add object, or request repair with saved prompts.
9. Export reviewed objects from the review step. Website package, MotionJSON,
   and other handoff cards remain review-gated.
10. Validate export settings in Advanced, then use the export handoff cards or
    `Export MotionJSON` to write reviewed local artifacts.
11. Use the Asset Library panel in Advanced to save useful generated/export artifacts as
    reusable motion layers, add them to brand collections, and assemble
    creator-approved packs when rights metadata permits.

Video registration copies the selected local file into the configured local
storage root and records rights source metadata for the upload. Missing paths
return a visible API error.

The guided UI no longer asks for a separate mask-provider choice in normal SAM
flows. Instead it derives the execution engine from the selected workflow and
the compatible model connection:

- `Trace one object`: prefers SAM2 local/hosted, but can route through
  `sam3_exemplar` with `provider.name = sam3-local` or `sam3-hosted`. Guided
  SAM3 single-object tracing is box-first.
- `Find by description`: defaults to hosted `sam3_concept` providers such as
  Roboflow SAM3, because the normal SAM3 Scene Sweep runtime does not understand
  text prompts. Advanced users can intentionally choose local `sam3_concept`
  only after installing the official SAM3 package and configuring a local
  `sam3.pt` checkpoint through `sam3ModelPath` / `SAM3_LOCAL_MODEL`.
- `Trace all objects`: defaults to `sam3_auto_masks` with SAM3 local/hosted and
  falls back to `auto_object_proposals` on local SAM2 when needed.
- `Find moving things`: uses the CPU/no-model `motion_foreground` workflow.
- `Import masks`: uses `external_masks` plus the `external` provider.

Real detector packages and weights remain optional and capability-gated for
legacy `text_detector` or `class_detector` compatibility flows under Advanced.

Model-generated plans are review artifacts, not trusted extraction truth. The
browser never receives raw hosted API keys, and hosted planners still require
server-side settings plus per-run network/cost confirmation before a hosted
request can run. The default fake/local planner makes no network call, returns
privacy and estimated-cost notes, and records `model_plan_attached` in the job
event log after the user confirms extraction.

## Build And Smoke

The frontend shell is static HTML/CSS/JavaScript packaged with the Python
distribution. It intentionally avoids remote resources and frontend runtime
dependencies.

```bash
npm run build
```

The root build script runs `node scripts/build_ui_shell.mjs`. The generated
shell is served by `motionjson ui` and packaged as Python package data:

```toml
[tool.setuptools.package-data]
motionjson = ["schemas/*.json", "ui/static/*", "ui/static/**/*"]
```

The build command checks that the static files are present, local routes are
referenced, and no remote resources are loaded by the shell. The recursive
package-data pattern keeps nested static assets available in installed Python
packages without requiring Node at runtime.

Useful command-surface checks:

```bash
motionjson ui --help
python3 -m motionjson.cli ui --help
```

Commercial layout smoke:

```bash
npm run ui:layout
```

For screenshot evidence across the supported viewport matrix:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-03b
```
