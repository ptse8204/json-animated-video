# MotionJSON Architecture Plan

## 1. Desired architecture

```text
                ┌──────────────────────────────┐
                │          Web UI              │
                │ React/TS video canvas,       │
                │ wizard, review, correction   │
                └──────────────┬───────────────┘
                               │ HTTP/WebSocket/SSE
                ┌──────────────▼───────────────┐
                │        Local API Server       │
                │ FastAPI or equivalent         │
                │ projects, jobs, artifacts     │
                └──────────────┬───────────────┘
                               │ shared services
┌──────────────────────────────▼───────────────────────────────┐
│                  MotionJSON Core Backend                     │
│ config, validation, pipeline, provider registry, jobs, export │
└───────┬──────────────┬──────────────┬──────────────┬─────────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
 candidate        mask providers   trackers      exporters
 providers        SAM2/mock/etc.   SAM2/etc.     MotionJSON/SVG/video
```

## 2. Main modules to introduce or refactor

Exact paths must be adapted after Phase 0 repository discovery. Suggested structure:

```text
motionjson/
  core/
    config.py              # typed run/project configs
    capabilities.py        # provider and environment diagnostics
    jobs.py                # job state, progress, artifact dirs
    artifacts.py           # artifact paths and metadata
    pipeline.py            # staged extraction pipeline
    tracks.py              # ObjectTrack, FrameShape, metrics
    fallback.py            # raster fallback reason codes
    validation.py          # MotionJSON/project validation
  providers/
    base.py                # provider protocols/interfaces
    mock.py                # deterministic test/demo providers
    manual.py              # manual point/box/mask candidate provider
    sam2_provider.py       # existing SAM2 wrapper refactored
    sam_auto_masks.py      # optional automatic mask proposal provider
    text_detector.py       # optional open-vocabulary detector bridge
    class_detector.py      # optional YOLO/known-class detector bridge
    motion_foreground.py   # simple moving-region provider
    external_masks.py      # import masks/boxes
  api/
    app.py                 # local server factory
    routes_health.py
    routes_projects.py
    routes_jobs.py
    routes_artifacts.py
  ui/                      # if frontend is vendored inside package
    package.json
    src/
  cli.py                   # preserves existing commands, adds `ui`
```

## 3. Typed config model

The UI and CLI should both generate the same config shape.

```python
class ExtractionRunConfig(BaseModel):
    input_video: Path
    output_dir: Path
    sample_fps: float | None = None
    max_frames: int | None = None
    device: Literal["auto", "cpu", "cuda", "mps"] = "auto"
    mode: Literal[
        "manual_prompt",
        "text_detector",
        "sam_auto_masks",
        "class_detector",
        "motion_foreground",
        "external_masks",
        "hybrid",
    ]
    prompts: list[PromptSpec] = []
    discovery: DiscoveryConfig
    tracking: TrackingConfig
    filtering: TrackFilterConfig
    export: ExportConfig
    debug: DebugConfig
```

### Prompt model

```python
class PromptSpec(BaseModel):
    object_id: str | None = None
    label: str | None = None
    frame_index: int = 0
    kind: Literal["point", "box", "mask", "positive_point", "negative_point"]
    data: dict
```

Examples:

```json
{"kind":"point","frame_index":0,"label":"red ball","data":{"x":410,"y":230}}
{"kind":"box","frame_index":0,"label":"ball","data":{"x1":390,"y1":210,"x2":430,"y2":250}}
```

## 4. Provider interfaces

### Candidate provider

```python
class ObjectCandidateProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapability: ...
    def propose(self, video: VideoSource, config: ExtractionRunConfig, ctx: RunContext) -> list[ObjectCandidate]: ...
```

### Mask provider

```python
class MaskProvider(Protocol):
    name: str

    def capabilities(self) -> ProviderCapability: ...
    def initialize_masks(self, video: VideoSource, candidates: list[ObjectCandidate], ctx: RunContext) -> list[InitialMask]: ...
```

### Video tracker

```python
class VideoTracker(Protocol):
    name: str

    def track(self, video: VideoSource, masks: list[InitialMask], config: TrackingConfig, ctx: RunContext) -> list[ObjectTrack]: ...
```

### Vectorizer

```python
class Vectorizer(Protocol):
    def vectorize(self, tracks: list[ObjectTrack], config: VectorizeConfig) -> list[ObjectTrack]: ...
```

### Exporter

```python
class Exporter(Protocol):
    def export(self, project: ProjectState, config: ExportConfig, ctx: RunContext) -> list[Artifact]: ...
```

## 5. Data model

### ObjectCandidate

```python
class ObjectCandidate(BaseModel):
    id: str
    label: str | None = None
    source: str
    frame_index: int
    box: Box | None = None
    mask_ref: str | None = None
    score: float | None = None
    metadata: dict = {}
```

### ObjectTrack

```python
class ObjectTrack(BaseModel):
    id: str
    label: str | None
    source: str
    frames: list[FrameShape]
    confidence: float | None = None
    warnings: list[str] = []
    include_in_export: bool = True
    metrics: TrackMetrics | None = None
```

### FrameShape

```python
class FrameShape(BaseModel):
    frame_index: int
    timestamp_sec: float
    box: Box | None = None
    centroid: Point | None = None
    mask_ref: str | None = None
    rle: dict | None = None
    contour: list[Point] | None = None
    area_ratio: float | None = None
    confidence: float | None = None
```

## 6. Pipeline stages

```text
validate config
  -> open video and sample frames
  -> discover candidates
  -> create initial masks
  -> propagate / track
  -> filter tracks
  -> deduplicate tracks
  -> vectorize masks/contours
  -> validate output
  -> export artifacts
```

Each stage should emit progress events and diagnostics.

## 7. Capability model

Every provider should expose capability information to CLI and UI.

```json
{
  "name": "sam2-local",
  "kind": "mask_provider",
  "available": false,
  "device": "cuda",
  "reasons": ["torch.cuda.is_available() returned false"],
  "install_hint": "Install the sam2 extra and check CUDA-enabled torch.",
  "supports": ["point", "box", "mask", "video_propagation"]
}
```

## 8. Local API endpoints

Suggested endpoints:

```text
GET  /api/health
GET  /api/capabilities
POST /api/projects
GET  /api/projects
GET  /api/projects/{project_id}
POST /api/projects/{project_id}/videos
GET  /api/projects/{project_id}/frames/{frame_index}
POST /api/projects/{project_id}/runs
GET  /api/jobs/{job_id}
GET  /api/jobs/{job_id}/events
POST /api/jobs/{job_id}/cancel
GET  /api/jobs/{job_id}/artifacts
GET  /api/artifacts/{artifact_id}
GET  /api/projects/{project_id}/tracks
PATCH /api/projects/{project_id}/tracks/{track_id}
POST /api/projects/{project_id}/tracks/merge
POST /api/projects/{project_id}/tracks/split
POST /api/projects/{project_id}/export
```

Use WebSocket or Server-Sent Events for progress if easy; otherwise polling is acceptable for the first UI release.

## 9. Project persistence

Suggested project directory:

```text
my_project.motionjson/
  project.json
  videos/
    input.mp4
  runs/
    2026-05-16T120000Z-manual-prompt/
      run_config.json
      events.jsonl
      logs.txt
      metrics.json
      candidates.json
      tracks.json
      output.motion.json
      preview.mp4
      masks/
      frames/
  exports/
```

A simple SQLite database can be added later for indexing, but plain files are easier to debug and commit to examples.

## 10. Frontend state model

Key state domains:

- `project`: selected project, video metadata, saved run configs.
- `capabilities`: providers, device, missing dependencies.
- `viewer`: current frame/time, zoom/pan, overlay visibility.
- `prompts`: user-created points, boxes, masks, labels.
- `runConfig`: selected mode and parameters.
- `jobs`: status, progress, logs, artifact links.
- `tracks`: object tracks, visibility, labels, warnings, edits.
- `export`: export options and validation status.

## 11. CLI relationship

The CLI should remain an expert/headless interface that uses the same config and pipeline.

Examples:

```bash
python -m motionjson.cli extract input.mp4 --config run_config.json
python -m motionjson.cli backend diagnostics --json
python -m motionjson.cli ui
```

Do not let UI logic become a separate implementation of extraction. UI should call API/backend services that share CLI code.

## 12. Dependency strategy

Base install:

- core package;
- CLI;
- validation;
- mock/simple providers;
- no heavy GPU dependencies.

Optional extras:

- `ui`: local server + frontend bundle dependencies;
- `sam2`: SAM2 and torch-compatible dependencies;
- `detectors`: open-vocabulary detector dependencies;
- `yolo`: known-class detector/segmenter dependencies;
- `dev`: tests, linting, build tools.

Heavy dependencies should be imported lazily inside provider modules.

## 13. Failure handling

Every failed run should write:

- `failure.json` with reason code and user message;
- `logs.txt` with detailed diagnostics;
- `run_config.json`;
- partial artifacts if useful.

Common reason codes:

```text
provider_unavailable
invalid_prompt
no_candidates
no_masks_accepted
whole_frame_mask_rejected
tracking_failed
vectorization_failed
export_failed
user_canceled
raster_mode_selected
```

## 14. Security and privacy

- Default processing is local.
- Do not send videos, frames, masks, prompts, logs, paths, or model tokens anywhere without explicit user opt-in.
- Store artifacts only under user-selected project/output directories.
- Sanitize file paths in the API.
- Avoid serving arbitrary local files through artifact endpoints.

## 15. Performance notes

- Use frame sampling for previews.
- Cache decoded frames for the viewer.
- Store masks compressed or RLE when possible.
- Allow lower-resolution preview modes.
- Cap object proposals by default.
- Provide low-VRAM options and warnings.

## 16. Migration path

1. Wrap current CLI extraction in typed config.
2. Add diagnostics without changing results.
3. Refactor stages behind interfaces.
4. Add mock providers to stabilize UI/tests.
5. Add UI that calls existing backend.
6. Add advanced providers and correction tools.
