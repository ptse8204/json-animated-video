# Local UI

The dependency-light local UI lets you inspect MotionJSON provider readiness,
create local projects, register source videos, draw prompts, start jobs, review
tracks, correct extraction results, export validated MotionJSON, and save
reusable motion layers. It runs against the existing SQLite backend and
filesystem storage. It does not require GPU, SAM2, hosted services, or network
access for the mock/no-model smoke path.

## Commercial Workspace Mode

The sidebar Workspace panel collects the product-level state a nontechnical
user needs before running extraction:

- recent projects, source videos, and jobs;
- guided tasks such as tracing one object, text-guided discovery, moving
  objects, and reviewing an existing result;
- saved local preferences for default goal, default mask provider, default
  export preset, and last project;
- provider-settings summary that keeps mock/no-model as the safe default;
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

The default workspace now starts with a goal-first wizard for nontechnical
users. The main canvas offers plain-language choices:

- Cut out one object.
- Find moving things.
- Find by description.
- Import masks.
- Review previous result.

The browser preview control is shown before backend path registration so users
can load a local file and draw prompts without understanding storage routes.
Backend extraction still requires a registered local path, which stays in an
Advanced disclosure with the registered video selector.

The Run preview panel shows a readable plan by default: goal, source status,
model/provider mode, prompt needs, review gate, and next steps. The generated
`ExtractionRunConfig` JSON remains available under Advanced for CLI and
developer users, but it is no longer the default explanation of what will run.

## Guided Workspace Flow

The Local UI now uses a progressive workflow instead of showing every setup,
diagnostic, review, correction, and export card at once. The main stepper
guides users through:

1. Choose goal.
2. Create or open project.
3. Add or select video.
4. Choose mode/provider.
5. Add prompts/keyframes.
6. Validate and run.
7. Review candidates/tracks.
8. Correct tracks.
9. Preview/export.

Only the active step's main panels are shown by default. Completed prior steps
appear as compact summary cards, and each step shows a next-action hint. The
`Show all panels` control restores the advanced dashboard view for power users
and debugging without removing the guided path.

The left navigation can collapse to a compact rail with the active goal and a
Menu button. The right details rail is collapsed by default on the first screen
and can be opened with `Show details`. When closed, hidden regions are removed
from the focus order. The workflow stepper supports ArrowRight, ArrowDown,
ArrowLeft, ArrowUp, Home, and End for keyboard navigation.

Diagnostics are quieter on successful runs but are not hidden when they matter.
Provider warnings stay visible before a run, failed runs open logs, and
fallback/raster/vector-unavailable diagnostics open automatically in the review
step.

## Model Setup Wizard

The main workspace includes a nontechnical Mode and model setup panel before
the extraction controls. It lists the safe `fake-local-planner` first, then
hosted planning options such as `openai-planner` and the settings-only
`openrouter-planner`. The local planner is selectable without credentials and
its test action performs a no-network readiness check.

Hosted planner cards show missing-key, settings-only, or ready status in plain
language before the user opens the advanced Provider settings rail. The setup
form saves model choice, optional base URL, API key replacement, and hosted
cost/privacy opt-in through `/api/provider-settings`; browser responses never
echo raw keys. `POST /api/model-providers/PROVIDER_ID/test` checks saved
server-side settings without making a hosted network call. A hosted model run
still requires the later per-run `allowNetwork` and cost/privacy
acknowledgement payload.

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
privacy summary, zero-local cost estimate, and `requiresUserConfirmation: true`.
The OpenAI connector treats model output as an untrusted proposal: MotionJSON
coerces it into explicit CV providers, generates the `ExtractionRunConfig`
locally, validates it, and still marks the plan as requiring user confirmation.
Segmentation and tracking remain routed through `mock`, `motion`, `external`,
or detector discovery modes; OpenAI does not segment video. All public model
responses pass through the Local UI sanitizer so API keys, bearer tokens, local
absolute paths, storage keys, and `file://` URIs are not returned to browser
code.

## Launch

Use the packaged console command for normal local UI sessions:

```bash
motionjson ui
```

Use the module entry point for deterministic CPU-only smoke checks:

```bash
python3 -m motionjson.cli ui --no-open --mock
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
  --no-open \
  --mock
```

The `--mock` flag keeps default run suggestions in no-model mode. It does not
pretend SAM2, CUDA, detectors, FFmpeg, or model weights are available; those
statuses still come from provider diagnostics.

On Windows PowerShell, use the module entry point after activating the virtual
environment:

```powershell
python -m motionjson.cli ui --no-open --mock
```

The sidebar First Run checklist summarizes base dependency readiness, no-model
provider availability, optional model extras, and FFmpeg status from
`/api/capabilities`. It also shows the recommended no-model command,
`python3 -m motionjson.cli ui --no-open --mock`, and keeps optional SAM2,
detector, hosted, and FFmpeg setup clearly marked as diagnostics instead of
claiming those providers are available in mock mode.

The local UI worker starts `mock`, `threshold`, `motion`, and `external`
extraction jobs, plus mock `auto_object_proposals`, `text_detector`,
`class_detector`, and `sam_auto_masks` discovery jobs that use generated mask
handoffs.
`motion_foreground` is CPU/no-model and runs from the `Find moving objects`
preset.

## Routes

The UI serves static files under `/ui/` and local JSON routes under `/api/`:

- `GET /api/health`
- `GET /api/capabilities`
- `GET /api/provider-settings`
- `POST /api/provider-settings`
- `DELETE /api/provider-settings/PROVIDER_ID`
- `POST /api/provider-settings/PROVIDER_ID/test`
- `GET /api/run-config/defaults`
- `POST /api/run-config/validate`
- `GET /api/exports/formats`
- `GET /api/projects`
- `POST /api/projects`
- `GET /api/videos?projectId=PROJECT_ID`
- `POST /api/videos`
- `GET /api/videos/VIDEO_ID/content`
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
videos are previewed through `/api/videos/VIDEO_ID/content`, which serves bytes
from local storage without exposing the storage path.
JSON, static shell, video, and artifact responses use local no-store headers.
The frontend only opens generated content links that point back to local
`/api/videos/.../content` or `/api/artifacts/.../content` routes.

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
models, and optional credentials without editing shell profiles. Mock/no-model
remains the default safe path. Local providers such as `mock`, `threshold`,
`motion`, and `external` do not accept API keys. Hosted providers show a cost
and privacy warning before they can be marked as allowed for hosted calls.

The Local UI currently exposes settings for:

- `mock`, `threshold`, `motion`, and `external`: local/free, no key required.
- `sam2-local`: local SAM2 model selection and diagnostics. Model weights and
  package setup still come from local environment paths.
- `sam2-hosted`: endpoint, model, API key, and explicit hosted-call opt-in.
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
confirmation, and the local extraction worker continues to run only
deterministic providers until runtime extraction routing is explicitly wired.
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

The default visible workflow is: choose a goal, create/open a project, add or
select video, choose mode/provider, add prompts/keyframes, validate and run,
review candidates/tracks, correct tracks, then preview/export. Advanced
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
3. Create or open a local project.
4. Add or select a source video. A browser preview helps with prompt drawing;
   backend jobs still require a registered local file path.
5. Choose mode/provider. Mock/local providers are shown first, and provider
   warnings stay visible before a run.
6. Add point, box, brush/erase mask, label, or keyframe prompts on the video
   overlay when the selected goal needs them. Prompt coordinates are native
   video pixels, not CSS canvas pixels.
7. Validate the generated plan before starting work. The raw
   `ExtractionRunConfig` JSON remains available under `View generated JSON`.
   The optional model plan panel can create a server-side local/mock plan from
   the selected goal and plain-language intent; generated configs are
   revalidated before `Confirm and start` can create a job.
8. Start a mock job for no-model smoke checks or start the configured provider
   run after validation passes.
9. Review candidates and tracks. Keep candidates, inspect track coverage and
   warnings, and use timeline markers before export.
10. Correct tracks if needed: relabel, hide/show, include/exclude from export,
    merge, split, add object, or request repair with saved prompts.
11. Validate export settings, then use the export handoff cards or
    `Export MotionJSON` to write reviewed local artifacts.
12. Use the Asset Library panel to save useful generated/export artifacts as
    reusable motion layers, add them to brand collections, and assemble
    creator-approved packs when rights metadata permits.

Video registration copies the selected local file into the configured local
storage root and records rights source metadata for the upload. Missing paths
return a visible API error.

Text prompts map to the `text_detector` discovery provider and do not route
directly to raw SAM2. In local UI mock mode, `Find objects from text` runs the
text detector mock path end to end: labels become candidate boxes, generated
mask sequences, object tracks, and a Candidates review panel sourced from
`candidates.json`. Real detector packages and weights remain optional and
capability-gated; missing detector diagnostics are still shown before a run.
Known-class presets map to `class_detector`. In local UI mock mode, `Find
known classes` records `class_preset`, custom classes, and confidence threshold
settings, creates generated candidate masks for the selected preset labels,
and sends those candidates through the same review/export path. Real YOLO or
known-class detector backends remain optional and capability-gated.
Automatic segment proposals map to `sam_auto_masks`. In local UI mock mode,
`Propose all visible segments` creates multiple generated proposal masks from
the selected keyframes, feeds them through track filtering/dedupe, and shows
the resulting candidate summary, tracks, fallback diagnostics, and merge
suggestions for review before export. Moving-object discovery maps to the
CPU/no-model `motion_foreground` workflow: frame differences become candidate
masks, candidate scores become track confidence, and low-quality/background
fragments remain visible through fallback diagnostics. External mask imports
use `external_masks` plus the `external` mask provider.

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
