# Local UI

Phase 7 introduced a dependency-light local UI shell for inspecting MotionJSON
provider readiness, creating local projects, registering source videos, and
viewing local job/progress state. Phase 8 adds a video prompt workspace and
goal-first extraction wizard that can build backend-validated run configs
before export. It runs against the existing SQLite backend and filesystem
storage. It does not require GPU, SAM2, hosted services, or network access for
the mock/no-model smoke path.

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
`/api/capabilities`.

## Routes

The UI serves static files under `/ui/` and local JSON routes under `/api/`:

- `GET /api/health`
- `GET /api/capabilities`
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
- `POST /api/jobs/JOB_ID/validate`
- `POST /api/jobs/JOB_ID/exports`
- `GET /api/artifacts?jobId=JOB_ID`
- `POST /api/projects/PROJECT_ID/imports/motionjson`

The local UI creates a reserved local user in the selected SQLite database and
uses that user for project, video, and job queries. API responses omit internal
storage keys, local `file://` storage URIs, and token material. Registered
videos are previewed through `/api/videos/VIDEO_ID/content`, which serves bytes
from local storage without exposing the storage path.

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

```json
{"operation": "split", "objectId": "object_0", "newObjectId": "object_0_tail", "frameRange": [24, 48]}
```

Corrections are stored in the local SQLite database and are returned from
`GET /api/jobs/JOB_ID/corrections` and the `correctionHistory` field on review
responses. Relabel, hide/show, delete, merge, and split update the editable
project review state used by local review and export-inclusion metadata.
`add_object` and `repair` are no-model partial-rerun hooks in this phase: the
request is persisted with `aiUsage: "none"` and `partialRerun.available:
false` instead of silently pretending that SAM2, detectors, or other ML
providers ran. The correction UI surfaces these repair and partial-rerun
diagnostics in the saved edit message and correction history.

`POST /api/jobs/JOB_ID/validate` validates the corrected export state without
writing new artifacts. It accepts the same `preset`, `includeMasks`,
`includeContours`, and `includePreview` fields as the export route so the
preflight reflects the exact handoff settings. `POST /api/jobs/JOB_ID/exports`
writes a validated MotionJSON handoff from the corrected review state,
registers the generated artifacts on the selected job, and returns public
content links for export files. The local UI supports these presets:

- `compact`: corrected `scene_graph.json`, final export manifest, validation
  report, and SVG overlay preview.
- `debug`: compact output plus contour/box JSON and copied cached mask PNGs.
- `vector-heavy`: corrected MotionJSON plus contour/box JSON for downstream
  vector tooling.
- `raster-fallback`: corrected MotionJSON plus mask and fallback-oriented
  diagnostics for runs where vector/object tracks need extra review.

Generated export JSON, ZIP assets, and generated overlay previews are safe to
open through `/api/artifacts/ARTIFACT_ID/content`; raw extraction JSON and
imported SVG files remain metadata-only unless they are part of this explicit
export workflow. Export manifests include
source job id, source asset id when known, preset, correction event count,
included/excluded object ids, sanitized run config/correction state, validation
status, and `aiUsage: "none"`. Local absolute paths and storage keys are
redacted from public export payloads.

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
6. Choose a wizard preset: `Trace one object`, `Find objects from text`,
   `Propose all visible segments`, `Find moving objects`, or `Import external
   masks`. Use `Review existing result` to import a previous MotionJSON file
   or output directory for inspection.
7. Draw point, box, brush/erase mask, label, or keyframe prompts on the video
   overlay. Prompt coordinates are native video pixels, not CSS canvas pixels.
8. Review the generated config and use `Validate config` to run backend
   validation plus provider availability checks before saving or starting work.
9. After a run succeeds, correct track labels/visibility/export inclusion if
   needed, validate the export preset, then use `Export MotionJSON` to write a
   validated local handoff with preview and optional contour/mask artifacts.

Video registration copies the selected local file into the configured local
storage root and records rights source metadata for the upload. Missing paths
return a visible API error.

Text prompts map to the `text_detector` discovery provider and do not route
directly to raw SAM2. Automatic segment proposals map to `sam_auto_masks` and
should be filtered before export. Moving-object discovery maps to the
CPU/no-model `motion_foreground` workflow. External mask imports use
`external_masks` plus the `external` mask provider.

## Build And Smoke

The frontend shell is static HTML/CSS/JavaScript packaged with the Python
distribution. It intentionally avoids remote resources and frontend runtime
dependencies in this phase.

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
