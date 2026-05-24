# Local UI

The dependency-light local UI lets you inspect MotionJSON provider readiness,
create local projects, register source videos, draw prompts, start jobs, review
tracks, correct extraction results, export validated MotionJSON, and save
reusable motion layers. It runs against the existing SQLite backend and
filesystem storage. The normal workflow is real-provider-first: connect local
SAM2/SAM3 or a hosted SAM provider in Model Connections, diagnose setup, then
validate the generated run config. Debug mock mode remains available only for
contributor smoke checks.

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

## Guided First Run

The default Local UI now opens in a 3-screen product flow:

1. `Setup`
2. `Prepare`
3. `Review`

`Setup` starts with a goal-first chooser for nontechnical users. The main
canvas offers plain-language choices:

- Cut out one object.
- Find moving things.
- Find by description.
- Import masks.
- Review previous result.

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

The Local UI now uses a progressive workflow instead of showing every setup,
diagnostic, review, correction, and export card at once. The main product flow
guides users through:

1. Start.
2. Video.
3. Model.
4. Prepare and run.
5. Review and export.

Guided mode now keeps one visible footer action per screen. The footer always
shows `Back` plus one explicit primary action such as `Add video`, `Continue`,
`Run trace`, `Run search`, `Run motion scan`, or `Export reviewed objects`.
Secondary actions such as demo video, diagnose, setup test, or review bulk
actions stay visually secondary inside the current panel.

After a run starts, the Job Center becomes part of the main workspace instead
of living only in the details rail. It shows the selected job, active/recent
jobs, normalized status, progress, provider, artifacts, and cancel state.
Failed runs switch the main screen to Run monitor, open the details rail, and
surface logs plus fallback diagnostics without requiring an extra discovery
step.

Local project creation is no longer a required early decision in guided mode.
When a user adds a video, starts from the bundled demo, or opens an existing
MotionJSON result, the Local UI creates a starter local project automatically
if one does not already exist. Manual project switching and manual project
creation remain available under `Project options` and `Show all panels`.

Only the active screen's main panels are shown by default. Advanced settings,
full diagnostics, raw config JSON, artifact browsing, correction history, and
export internals now sit behind the top-bar `Advanced` switch instead of
competing with the normal user path.

The left navigation can collapse to a compact rail with the active goal and a
Menu button. The right details rail is collapsed by default on the first screen
and can be opened with `Show details`. When closed, hidden regions are removed
from the focus order. The workflow stepper supports ArrowRight, ArrowDown,
ArrowLeft, ArrowUp, Home, and End for keyboard navigation.

Diagnostics are quieter on successful runs but are not hidden when they matter.
Provider warnings stay visible before a run, failed runs open logs, and
fallback/raster/vector-unavailable diagnostics open automatically in the Run
monitor or review step.

## Model Connections

The main workspace includes a nontechnical Model Connections panel before the
extraction controls. It recommends concrete SAM providers by workflow:

- Trace one object: `sam2-local` when checkpoint/config paths are ready,
  otherwise Replicate `replicate-sam2-video`.
- Find objects from text: `sam3-local` when the SAM3 package/model/runtime are
  ready, otherwise Roboflow `roboflow-sam3-pcs`.
- Frame-by-frame SAM3 image fallback: Fal `fal-sam3-image`.
- Custom SAM2/SAM3-compatible endpoints stay in the advanced provider list.

The form saves local model paths, selected profile/model, optional endpoint,
API key replacement, and hosted cost/privacy opt-in through
`/api/provider-settings`; browser responses never echo raw keys. Diagnose
checks use `POST /api/provider-settings/PROVIDER_ID/diagnose` and make no
hosted network calls. Hosted smoke tests require `allowNetwork`,
`allowHosted`, and `acknowledgeCostPrivacy`; local SAM smoke tests require
`allowHeavyLocal` before importing heavy model runtimes.

The guided workflow derives run config from a normalized connection contract:
connection ID, provider ID, engine, display label, hosted profile, locality,
capability flags, readiness, and hosted-call opt-in remain separate. Display
labels such as `Roboflow SAM3` are user-facing only; policy and validation use
provider IDs and connection IDs.

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

The local UI worker starts `sam2-local`, `sam2-hosted`, `sam3-local`,
`sam3-hosted`, `threshold`, `motion`, and `external` extraction jobs.
Discovery-owned SAM3 runs still route through the same review/filter/link/export
path, but the saved run config now records the selected SAM3 engine directly in
`provider.name` plus `provider.sam3` instead of hiding it behind a threshold
placeholder. `motion_foreground` is CPU/no-model and runs from the
`Find moving objects` preset.

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
- `sam3-local`: local SAM3 `sam3.pt` checkpoint file path, device,
  Python/CUDA/Hugging Face access diagnostics, and official setup commands.
  Use the resolved local checkpoint path for `SAM3_LOCAL_MODEL`, not the
  `/content/sam3` source checkout or the `facebook/sam3` Hugging Face repo id.
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
  preview when relevant, and a `Show all panels` dashboard escape hatch;
- collapsible right details rail for run monitor, review, corrections, export,
  asset library, logs, artifacts, and route diagnostics.

The default visible workflow is: choose a goal, add or select a video, connect
one compatible model when needed, prepare the run, then review and export.
Advanced
parameters, raw config JSON, raw routes, generated artifacts, library
management, logs, fallback diagnostics, and correction history remain available
through disclosure panels instead of being expanded by default.

Post-run work is grouped into a compact review sequence: run monitor, candidate
review, track review, corrections, and export. Clean runs keep logs and
generated artifacts collapsed. Failed runs and raster/vector fallback states
surface diagnostics immediately so users can see why object tracks were not
available.

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
2. Choose a goal from the first step. `Cut out one object` is the default safe
   path; `Find moving objects`, `Import external masks`, and `Review existing
   result` can run without optional ML models.
3. Add or select a source video. Guided mode creates a starter local project
   automatically the first time it needs one. MotionJSON prepares a browser-safe
   preview automatically before `Prepare` and `Review` open.
4. Choose mode/provider in Model Connections when the goal needs one. The UI
   recommends SAM2 local or
   Replicate for point/box tracing, SAM3 local or Roboflow for text concepts,
   and Fal SAM3 image as a hosted frame fallback. Provider warnings stay
   visible before a run.
5. Add point, box, brush/erase mask, label, or keyframe prompts on the video
   overlay when the selected goal needs them. Prompt coordinates are native
   video pixels, not CSS canvas pixels.
6. Start extraction from the footer after the generated plan validates. The raw
   `ExtractionRunConfig` JSON remains available under `View generated JSON`.
   The optional advanced model plan panel can create a server-side planner
   config from the selected goal and plain-language intent; generated configs are
   revalidated before `Confirm and start` can create a job.
7. Review candidates and tracks. Keep candidates, inspect track coverage and
   warnings, and use timeline markers before export.
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
- `Find by description`: defaults to `sam3_concept` with `provider.name =
  sam3-local` or `sam3-hosted`. Roboflow SAM3 is the recommended hosted concept
  provider, and Fal SAM3 image remains a sampled-frame fallback for text-led
  segmentation.
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
