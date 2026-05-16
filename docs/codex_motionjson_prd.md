# MotionJSON Product Requirements — UI + Multi-Object Video Tracing

## 1. Product vision

MotionJSON should let users turn a video into structured, inspectable object motion data without needing to memorize model-specific CLI flags. Users should be able to load a video, choose what they want to trace, run an extraction method, review the result, correct mistakes, and export MotionJSON plus useful debug artifacts.

The product should support expert CLI workflows, but the primary adoption path should be a local UI.

## 2. Problem statement

The current workflow is fragile for non-expert users:

- Users copy multiline commands into PowerShell/Bash and hit shell-specific errors.
- A SAM2 point prompt can accidentally identify background or the whole frame.
- The user expectation “trace every object” is not supported by single-point SAM2 tracking.
- Failures collapse into raster-only output without enough diagnostics.
- Users cannot easily inspect masks, object identities, confidence, frame coverage, or why vector/object extraction failed.
- There is no guided choice between manual prompt tracking, text-guided detection, automatic mask proposals, YOLO-style detection, and motion-only tracing.

## 3. Target users

### User A — Non-technical creator

Wants to trace moving objects from short videos for creative animation, overlays, game assets, or visual analysis. Needs a clear UI, examples, and simple presets.

### User B — ML/vision hobbyist

Wants to experiment with SAM2, detectors, and tracking without rewriting scripts. Needs advanced controls and diagnostics.

### User C — Developer/integrator

Wants reproducible MotionJSON outputs for downstream apps. Needs CLI parity, project config, stable schemas, and headless job support.

### User D — Research/eval user

Wants to compare extraction modes, run benchmarks, and inspect failure cases. Needs debug artifacts, metrics, and repeatable configs.

## 4. Jobs to be done

- “I have a video and want to trace one object accurately.”
- “I have a video and want the app to find the objects for me.”
- “I know the objects I care about, such as `red ball`, `hand`, and `cup`, and want to trace those.”
- “I only care about moving objects.”
- “The automatic result is wrong; I need to correct it without restarting from scratch.”
- “I need to export a clean MotionJSON file and verify it before using it elsewhere.”

## 5. Definitions

### MotionJSON object track

A temporally linked entity with stable ID, label, per-frame mask/contour/box/centroid data, confidence, source method, and export metadata.

### Raster fallback

An output mode where the full frame or rendered video is exported as raster data because object/vector tracks are unavailable or rejected. Raster fallback must be explicit and diagnosed.

### Object discovery

The process of proposing candidate objects before tracking. This can come from text detection, automatic masks, known-class detectors, or motion segmentation.

### Object tracking

The process of maintaining stable identity and mask/shape information across frames.

### “Every object”

A user phrase that must be disambiguated through presets:

- **Semantic objects:** objects with human-recognizable labels.
- **Moving objects:** foreground things changing over time.
- **Visible segments:** every segment proposed by a segmentation model.
- **Text labels:** objects matching a user prompt.
- **Known detector classes:** classes supported by a selected detector.

## 6. Goals

### G1. Guided extraction UI

Users can load a video, choose a goal, configure relevant options, run extraction, watch progress, and inspect results.

### G2. Multi-approach backend

The backend supports multiple extraction methods through stable provider interfaces rather than hard-coded CLI branches.

### G3. Review and correction

Users can review object tracks, hide/delete bad tracks, relabel objects, merge duplicates, split incorrect identities, add missing objects, and re-run repair on selected frames/tracks.

### G4. Transparent diagnostics

The app surfaces provider availability, model/device status, logs, frame-level quality, and reasons for raster fallback.

### G5. Reproducible export

Every run has a validated config, output artifacts, metrics, logs, and reproducible command/project metadata.

### G6. Adoption

The project includes sample videos, guided tutorials, one-click presets, CPU/mock demos, docs, and platform-friendly launchers.

## 7. Non-goals for the first release

- Cloud-hosted processing.
- Fully automatic perfect semantic understanding of arbitrary videos.
- Training custom detectors inside the UI.
- Frame-perfect professional rotoscoping tools equivalent to After Effects.
- Real-time production tracking for long videos.

These can be future features, but the roadmap should prioritize a stable local app and transparent workflows first.

## 8. Primary product flows

### Flow 1 — Trace one object

1. User opens a video.
2. App shows first frame and backend readiness.
3. User chooses “Trace one object.”
4. User places a point, draws a box, or paints a rough mask.
5. App previews initial mask.
6. User accepts or adds negative/positive corrections.
7. App tracks across video.
8. User reviews timeline coverage and exports.

### Flow 2 — Find objects from text

1. User opens a video.
2. User chooses “Find objects from text.”
3. User enters labels like `red ball . hand . table .` or uses chips.
4. Detector proposes boxes/masks on keyframes.
5. User approves candidate objects.
6. SAM2 or tracker propagates masks.
7. User reviews tracks and exports.

### Flow 3 — Propose all visible segments

1. User chooses “Propose all visible segments.”
2. App warns that walls/floors/background fragments may appear.
3. Automatic mask generator proposes candidate masks.
4. App filters by area, stability, duplicate overlap, and background likelihood.
5. User keeps/deletes candidates.
6. App tracks and exports.

### Flow 4 — Find moving objects

1. User chooses “Find moving objects.”
2. App runs motion segmentation on sampled frames.
3. App groups moving regions into candidates.
4. User approves/relabels candidates.
5. App tracks and exports.

### Flow 5 — Review/correct bad result

1. User opens an existing project or result.
2. App shows tracks, masks, confidence, and failure/raster diagnostics.
3. User selects a bad track.
4. User repairs with point/box/mask on a keyframe, or splits/merges tracks.
5. App re-runs only the affected track/range.
6. User exports final MotionJSON.

## 9. UX success criteria

- A user can load `examples/demo_red_ball.mp4` and extract the ball without typing a CLI command.
- A user can see whether the app is using CPU or CUDA and whether SAM2 is actually available.
- A user can understand why a result became raster-only.
- A user can run at least one demo workflow without downloading large models, using mock/synthetic output.
- A user can discover and trace multiple objects through a guided workflow.
- A user can export MotionJSON and a preview video from the UI.

## 10. Engineering success criteria

- Extraction modes share typed configs and provider interfaces.
- CLI and UI use the same backend services.
- Test suite includes mock providers and synthetic fixtures.
- Heavy dependencies are optional extras and reported by capability endpoints.
- UI can run in a no-GPU environment for smoke tests.
- Every phase has a commit and phase report.

## 11. Metrics

### Product metrics

- Time from install to first successful export.
- Number of clicks/steps to run demo extraction.
- Percentage of runs with clear success/failure status.
- Number of raster-only fallbacks that include actionable diagnostics.

### Technical metrics

- Per-frame mask coverage.
- Track continuity / dropped-frame count.
- Duplicate track overlap.
- Average object confidence/stability.
- Runtime and memory usage by provider.
- Export validation pass/fail.

## 12. Release readiness

A release candidate is ready when:

- CLI still works.
- UI launches locally from a documented command.
- At least three extraction workflows are usable: single prompt, auto mask proposal/mock, and text/motion/detector path depending on dependency availability.
- Tests pass without GPU.
- GPU/provider diagnostics are truthful.
- Docs include Windows PowerShell examples and troubleshooting.
- A user can run the red-ball demo through the UI and export a MotionJSON file.
