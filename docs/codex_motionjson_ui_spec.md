# MotionJSON UI Specification

> Historical/reference UI spec. It may describe older screens and panel shapes.
> Use `docs/product/ui_redesign_brief.md` for current redesign behavior
> requirements.

## 1. UI objective

The UI should make object tracing feel like a guided visual workflow, not a CLI flag puzzle. It should expose the right concepts: project, video, goal, extraction mode, provider readiness, prompts, candidates, tracks, corrections, and exports.

## 2. Information architecture

```text
Home / Recent Projects
  ├─ New Project Wizard
  ├─ Open Project
  └─ Example Projects

Project Workspace
  ├─ Setup / Capabilities
  ├─ Video + Prompt Canvas
  ├─ Extraction Wizard
  ├─ Job Progress + Logs
  ├─ Results Review
  ├─ Correction Tools
  └─ Export
```

## 3. Main screens

### 3.1 Home

Purpose: help users start quickly.

Elements:

- New Project button.
- Open Project button.
- Recent projects list.
- Example projects:
  - Red ball demo.
  - Multiple moving shapes demo.
  - Text-detect demo if dependencies are available.
  - Mock demo for users without ML dependencies.
- Provider status summary: core OK, UI OK, FFmpeg/video IO, SAM2, CUDA, detectors.

### 3.2 New Project Wizard

Steps:

1. Select video.
2. Name project and choose project/output directory.
3. Analyze video metadata: dimensions, FPS, duration, frame count, codec.
4. Show first frame and backend readiness.
5. Choose extraction goal.

Validation:

- Video must be readable.
- Output path must be writable.
- Warn if video is long/heavy and suggest sampling.

### 3.3 Extraction Goal Chooser

Cards:

#### Trace one object

Use when the user can point to/draw around the object. Uses manual point/box/mask prompts and SAM2/mask provider tracking.

#### Find objects from text

Use when the user knows labels. Example prompt: `red ball . hand . cup .`. Requires a text detector provider.

#### Propose all visible segments

Use when the user wants broad segmentation. Warns that background fragments may appear.

#### Find moving objects

Use when objects move relative to the background. Works even without semantic labels.

#### Import masks/boxes

Use when masks/boxes came from another tool.

#### Review existing result

Use when opening a previous MotionJSON/project output.

### 3.4 Video workspace

Layout:

```text
┌──────────────── Toolbar ────────────────┐
│ Select | Point | Box | Brush | Eraser    │
│ Positive | Negative | Label | Keyframe   │
└─────────────────────────────────────────┘
┌─────────────┬───────────────────────────┐
│ Left panel  │ Video/canvas viewer       │
│ Goal/config │ overlays + prompts        │
│ Providers   │                           │
├─────────────┴───────────────────────────┤
│ Timeline: frames, prompts, tracks, jobs │
└─────────────────────────────────────────┘
┌───────────── Right panel ───────────────┐
│ Tracks, logs, artifacts, export         │
└─────────────────────────────────────────┘
```

Viewer requirements:

- Show current frame.
- Overlay prompts, boxes, masks, contours, centroids, labels.
- Zoom and pan.
- Toggle overlays by track/provider.
- Display pixel coordinates under cursor.
- Display video coordinate system, not CSS-scaled coordinates.
- Support keyboard navigation frame-by-frame.

### 3.5 Prompt tools

#### Point tool

- Click creates point prompt.
- Prompt has label and object ID.
- User can mark point as positive or negative.
- Show coordinate as `x,y`.

#### Box tool

- Drag rectangle.
- Show dimensions.
- Snap/resize handles.
- Useful for small objects like a ball.

#### Brush/mask tool

- Paint rough mask.
- Erase.
- Adjustable brush size.
- Mask can initialize SAM2/tracker.

#### Label tool

- Assign label to selected prompt/candidate/track.
- Suggested labels from text prompt chips.

#### Keyframe tool

- Mark frame as discovery/repair keyframe.
- Allow different prompts on different frames.

### 3.6 Extraction Wizard panel

Shows mode-specific fields.

#### Manual prompt mode fields

- Prompt type: point, box, mask.
- Object label.
- Frame index.
- Mask provider: auto/SAM2/local/mock.
- Device: auto/cpu/cuda/mps.
- Sample FPS.
- Max frames.
- Preview initial mask button.

#### Text detector mode fields

- Text prompt chips.
- Raw prompt string.
- Detector provider.
- Box threshold.
- Text threshold.
- Keyframes to run discovery on.
- Maximum objects.
- Deduplicate candidates toggle.
- Send candidates to SAM2 toggle.

#### Auto masks mode fields

- Keyframe selection.
- Minimum mask area.
- Maximum mask area ratio.
- Stability threshold.
- Duplicate IoU threshold.
- Maximum proposals.
- Background rejection toggle.

#### Class detector mode fields

- Detector provider.
- Class list.
- Confidence threshold.
- Tracking method.
- Segmentation on/off.

#### Motion foreground mode fields

- Sensitivity.
- Minimum blob area.
- Background model frames.
- Morphology cleanup.
- Maximum objects.

### 3.7 Capability status UI

Each provider has a status chip:

- Ready.
- Available but CPU-only.
- Missing dependency.
- Missing model.
- Device unavailable.
- Unsupported on this platform.
- Not configured.

Clicking a chip shows:

- reason;
- install hint;
- relevant command/docs;
- whether mock mode can be used.

### 3.8 Run progress UI

Pipeline stages:

1. Validating config.
2. Reading video.
3. Sampling frames.
4. Discovering candidates.
5. Initializing masks.
6. Tracking/propgating.
7. Filtering/deduplicating.
8. Vectorizing.
9. Exporting.
10. Validating output.

Show:

- current stage;
- frame progress;
- elapsed time;
- logs;
- cancel button;
- artifact links as they become available.

### 3.9 Results Review

Track list columns:

- visibility toggle;
- color swatch;
- label;
- source;
- confidence;
- frames covered;
- warnings;
- include in export.

Track details:

- preview thumbnail;
- frame coverage chart;
- area over time;
- confidence over time;
- source prompts/candidates;
- warnings such as `whole-frame-like mask`, `short track`, `duplicate overlap`.

Viewer overlays:

- mask fill;
- contour;
- box;
- centroid trail;
- labels;
- confidence heat/alpha.

### 3.10 Correction tools

Required actions:

- Hide/show track.
- Include/exclude from export.
- Rename/relabel.
- Delete track.
- Merge selected tracks.
- Split track at frame.
- Split by selected frame range.
- Add missing object from prompt.
- Repair selected track on selected frame range.
- Undo/redo recent edits if feasible.

Correction history should be saved in project state.

### 3.11 Export screen

Options:

- MotionJSON output path.
- Include masks: none/RLE/files.
- Include contours.
- Include boxes/centroids.
- Include raster fallback if needed.
- Include debug metadata.
- Generate preview video.
- Generate SVG/frame overlays.
- Validate before export.

Export result:

- validation status;
- artifact list;
- open folder button if supported;
- copy CLI equivalent/config path.

## 4. Error states

### Invalid prompt

Example: point outside video bounds, no prompt selected, box too small.

UI message: “The point is outside the video frame. Place the point inside the object on the displayed frame.”

### Provider unavailable

UI message: “SAM2 local is not available because CUDA is not detected and the selected device is CUDA. Switch to CPU/auto or fix CUDA.”

### Whole-frame mask

UI message: “The selected mask covers 96% of the frame, so it was rejected as likely background/whole-frame. Try a tighter box or a point inside the object with negative points on the background.”

### Raster fallback

UI message: “MotionJSON exported raster-only because no object tracks passed filtering. Review candidate filters or add manual prompts.”

### Long video warning

UI message: “This video is long. Start with a sampled preview run, then increase max frames after you confirm the objects are correct.”

## 5. Keyboard shortcuts

Suggested defaults:

```text
Space        Play/pause preview
Left/Right   Previous/next frame
Shift+Left   Previous keyframe
Shift+Right  Next keyframe
V            Select tool
P            Point tool
B            Box tool
M            Brush/mask tool
E            Eraser
+/-          Zoom in/out
H            Hide selected track
Delete       Delete selected prompt/track after confirmation
Ctrl+Z       Undo
Ctrl+Y       Redo
```

## 6. UX copy for extraction modes

### Trace one object

“Best when you can point to or draw around the object. Most reliable for a specific object.”

### Find objects from text

“Best when you know what objects you want. Enter object names like `red ball . hand . table .`.”

### Propose all visible segments

“Broadest mode. May include background pieces, shadows, and object parts. Review before export.”

### Find moving objects

“Best when objects move. Does not understand labels, but can find foreground motion.”

### Mock demo mode

“Runs without large models. Useful for testing the UI and export flow.”

## 7. Accessibility and usability

- All buttons and inputs need accessible labels.
- Track colors should not be the only identity cue; use labels and patterns/icons.
- Keyboard navigation should work for main panels.
- Logs should be selectable/copyable.
- Progress should not rely only on color.
- Provide reduced-motion option for preview animations.

## 8. Frontend testing goals

- Render home screen.
- Render capability status.
- Build a run config from each wizard mode.
- Draw prompt coordinate correctly on a scaled canvas.
- Start mock job and display result track.
- Toggle track visibility and export inclusion.
- Show raster fallback diagnostic.
