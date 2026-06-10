# MotionJSON Multi-Object ML Pipeline Specification

> Historical/reference spec. Current extraction and provider truth lives in
> `docs/codex/CURRENT_ARCHITECTURE.md`, `src/motionjson/pipeline.py`, and
> `src/motionjson/providers/`.

## 1. Core insight

SAM2-style video segmentation is excellent for “given this object, track it.” It is not, by itself, a complete answer to “find every object in this video.” MotionJSON needs explicit object discovery modes before segmentation/tracking.

The product should expose “trace every object” as a set of presets, each backed by a different pipeline.

## 2. Pipeline modes

### 2.1 Manual prompt tracking

**User intent:** “Trace this specific object.”

**Inputs:** point, box, mask, positive/negative points, frame index, label.

**Pipeline:**

```text
manual prompt -> initial mask provider -> video tracker -> track filter -> vectorizer -> export
```

**Strengths:** reliable for user-selected objects.

**Weaknesses:** does not discover objects automatically.

**UI label:** Trace one object.

### 2.2 Text-guided discovery + SAM2

**User intent:** “Trace the objects I can describe.”

**Inputs:** text labels/chips such as `red ball . hand . cup .`, thresholds, keyframes.

**Pipeline:**

```text
keyframes -> text detector boxes -> candidate filter -> SAM2 initial masks -> video tracker -> dedupe -> vectorizer -> export
```

**Strengths:** matches user idea of natural-language object selection.

**Weaknesses:** depends on detector availability and prompt quality.

**UI label:** Find objects from text.

**Prompt guidance:** Category phrases should be separated clearly. Avoid vague prompts like “everything” unless provider supports generic objectness.

### 2.3 Automatic mask proposals

**User intent:** “Show me everything the segmenter can see.”

**Inputs:** keyframes, area thresholds, stability thresholds, max proposals.

**Pipeline:**

```text
keyframes -> automatic mask generator -> reject huge/tiny/duplicate/background masks -> initialize tracks -> propagate -> review -> export
```

**Strengths:** no labels required.

**Weaknesses:** may include background, shadows, texture patches, object parts, or duplicate masks.

**UI label:** Propose all visible segments.

### 2.4 Known-class detector/segmenter tracking

**User intent:** “Trace common objects like person, car, cup, ball if the detector knows them.”

**Inputs:** class list, detector provider, confidence threshold, tracking settings.

**Pipeline:**

```text
frames -> detector/segmenter -> tracker/linker -> optional SAM2 refinement -> vectorizer -> export
```

**Strengths:** fast and familiar if classes are supported.

**Weaknesses:** limited to model classes unless fine-tuned.

**UI label:** Known classes.

### 2.5 Motion foreground discovery

**User intent:** “Find things that move.”

**Inputs:** sensitivity, min area, background frames, cleanup settings.

**Pipeline:**

```text
sampled frames -> motion masks/blobs -> blob linking -> optional SAM2 refinement -> vectorizer -> export
```

**Strengths:** works without semantic model; useful for simple videos.

**Weaknesses:** camera motion, shadows, lighting changes, and stationary objects can fail.

**UI label:** Moving objects.

### 2.6 External masks/boxes

**User intent:** “Use masks or boxes from another tool.”

**Inputs:** mask files, box JSON/CSV, labels, frame mapping.

**Pipeline:**

```text
external annotations -> validation -> track/link/refine -> export
```

**Strengths:** interoperability.

**Weaknesses:** frame alignment and format issues.

**UI label:** Import masks/boxes.

## 3. Hybrid mode

A future “Smart All Objects” mode can combine providers:

```text
text detector + auto masks + motion foreground
  -> normalize candidates
  -> score candidates
  -> dedupe by IoU and temporal overlap
  -> ask user to approve candidates
  -> track/refine/export
```

Default hybrid should remain conservative to avoid noisy exports.

## 4. Candidate representation

All discovery providers should output the same object candidate schema.

```json
{
  "id": "cand_001",
  "source": "text_detector",
  "label": "red ball",
  "frame_index": 0,
  "score": 0.91,
  "box": {"x1": 390, "y1": 210, "x2": 430, "y2": 250},
  "mask_ref": null,
  "metadata": {
    "prompt": "red ball . hand .",
    "provider": "grounding_dino"
  }
}
```

## 5. Candidate filtering

Default filters:

- Reject masks smaller than `min_mask_area_px`.
- Reject masks larger than `max_mask_area_ratio`, for example 0.60 unless user chooses all-segments debug mode.
- Reject near-duplicates by IoU threshold.
- Prefer higher score/stability candidates.
- Cap number of candidates per keyframe and total.
- Flag background-like masks.
- Keep user prompts even when filters are strict, but warn if they look suspicious.

## 6. Track linking and identity

Multi-object pipelines need stable IDs.

Basic strategy:

1. Each approved candidate creates a provisional object ID.
2. Tracker propagates masks across frames.
3. Link tracks across keyframes by IoU, centroid motion, label, and confidence.
4. Merge duplicates if overlap is high over time.
5. Flag identity switches or track fragmentation.

Track IDs should be stable within a project:

```text
obj_0001
obj_0002
obj_0003
```

Labels can change without changing ID.

## 7. Vectorization

Masks should be converted to contours when requested.

Recommended steps:

- choose largest connected component or preserve multiple components based on config;
- simplify contours with tolerance;
- remove tiny holes/fragments;
- store area, centroid, and bbox metrics;
- validate contours are inside frame bounds.

If vectorization fails but masks exist, do not silently rasterize. Export masks if configured and show vectorization failure reason.

## 8. Raster fallback policy

Raster fallback should be an explicit state, not a silent default.

Reasons:

```text
no_candidates
no_masks_accepted
whole_frame_mask_rejected
tracking_failed
vectorization_failed
provider_unavailable
user_selected_raster
```

Each reason should include suggested fixes.

Example:

```json
{
  "fallback": "raster_only",
  "reason_code": "whole_frame_mask_rejected",
  "message": "The only accepted mask covered 94% of the frame, so object extraction was rejected.",
  "suggestions": [
    "Use a tighter box around the object.",
    "Add negative points on the background.",
    "Lower max_mask_area_ratio only if you intentionally want large regions."
  ]
}
```

## 9. Provider capability checks

Each provider should declare:

- installed/importable;
- model weights available;
- supported devices;
- supported prompt types;
- supported input/output shapes;
- estimated memory needs if known;
- install hints;
- whether mock mode is available.

## 10. Debug artifacts

Every run should be able to produce:

- keyframe images;
- candidate overlays;
- initial mask overlays;
- track overlays;
- rejected candidate list with reasons;
- metrics JSON;
- events JSONL;
- logs;
- preview video.

## 11. Minimum viable implementations by mode

### Manual prompt

Must be real if current SAM2 provider exists; otherwise mock mode for UI.

### Text detector

Can start as an interface + mock provider + optional implementation. Do not block UI on detector dependencies.

### Auto masks

Can start with mock/simple mask proposal; later wire real SAM2 automatic mask generator or equivalent.

### Class detector

Can start as interface + optional provider.

### Motion foreground

Should be feasible with OpenCV/simple image differences and no heavy ML dependency. This is a good early real non-manual mode.

### External masks

Can start with JSON boxes/masks import before supporting every mask format.

## 12. Benchmark scenarios

- One red ball on static background.
- Two colored balls crossing paths.
- Object partly occluded.
- Small object with blur.
- Person/hand interacting with object.
- Camera motion without object motion.
- Background texture that confuses automatic masks.
- Whole-frame failure case.

## 13. Model/provider examples for future integration

These should remain optional and swappable:

- SAM2 local/Hugging Face video segmentation/tracking.
- Open-vocabulary text detectors such as GroundingDINO-style providers.
- Known-class detectors/segmenters such as YOLO-style providers.
- Classical OpenCV motion segmentation.

Do not hard-code one vendor/model as the only path.
