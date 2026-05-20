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
- `openrouter`: LLM/VLM model selection and API key for reasoning only. It is
  not a mask or segmentation provider.
- `text_detector` and `class_detector`: local model settings for scaffolded
  detector surfaces. They remain capability-gated until concrete dependencies
  and adapters are configured.

Provider settings are stored in the selected local SQLite database for the
reserved Local UI user. Raw keys are never returned by `/api/provider-settings`,
`/api/capabilities`, validation responses, screenshots, or error messages.
Environment variables take precedence over local UI settings for headless/CLI
work. Saved hosted keys are currently settings-only for diagnostics; the local
worker still runs only deterministic providers until runtime provider routing
is explicitly wired. See [Provider API keys](security/api_keys.md) for storage,
redaction, deletion, and hosted-provider guidance.

## Product Shell

The commercial Local UI shell is organized around a stable app frame:

- left goal rail for tracing modes and first-run readiness;
- main workspace for project/video setup, preview tools, extraction settings,
  and run config preview;
- right inspector for run monitor, review, artifacts/export, corrections,
  asset library, and route diagnostics.

The visible workflow is: create or open a project, add video, choose mode/model,
confirm locality, run, review candidates, correct tracks, preview, and export.
Advanced parameters, raw routes, library management, review panels, and
correction history are available through native disclosure panels instead of
being expanded by default.

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
diagnostics in the saved edit message and correction history.

`POST /api/jobs/JOB_ID/validate` validates the corrected export state without
writing new artifacts. It accepts the same `preset`, `includeMasks`,
`includeContours`, and `includePreview` fields as the export route so the
preflight reflects the exact handoff settings. The response includes
`qualityRouting`, which explains the cached raster/vector/delivery/preview
route that export will use. MP4 preview validation is a dry run: it reports
`plan_ready` when FFmpeg is available and encodes only during final export.
The response also includes `rightsSummary` and `exportWarnings` so unverified
source attribution, creator approval, license, and commercial-use status are
visible before handoff.
`POST /api/jobs/JOB_ID/exports` writes a validated MotionJSON handoff from the
corrected review state, registers the generated artifacts on the selected job,
and returns public content links for export files. The local UI supports these
presets:

- `compact`: corrected `scene_graph.json`, final export manifest, validation
  report, and SVG overlay preview.
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
status, rights warnings, and `aiUsage: "none"`. Local absolute paths and
storage keys are redacted from public export payloads. The export panel and
selected-track detail surface rights status without requiring users to open raw
JSON.

`POST /api/projects/PROJECT_ID/imports/motionjson` imports an existing
MotionJSON file or output directory into a succeeded `motionjson_import` job
for review. It validates the supplied path, copies the result into local
storage, and exposes the imported scene through the normal job review routes.

## Project And Video Flow

1. Open the UI command above.
2. Confirm health and capability diagnostics are visible.
3. Create a project from the project panel.
4. Add a source video by entering an existing local file path.
5. Select the video from the video picker or video list.
6. Choose a wizard preset: `Trace one object`, `Find objects from text`, `Find
   known classes`, `Propose all visible segments`, `Find moving objects`, or
   `Import external masks`. Use `Review existing result` to import a previous
   MotionJSON file or output directory for inspection.
7. Draw point, box, brush/erase mask, label, or keyframe prompts on the video
   overlay. Prompt coordinates are native video pixels, not CSS canvas pixels.
8. Review the generated config and use `Validate config` to run backend
   validation plus provider availability checks before saving or starting work.
9. After a run succeeds, correct track labels/visibility/export inclusion if
   needed, validate the export preset, then use `Export MotionJSON` to write a
   validated local handoff with preview and optional contour/mask artifacts.
10. Use the Asset Library panel to save useful generated/export artifacts as
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
