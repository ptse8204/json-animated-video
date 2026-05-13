# MotionJSON Product Requirements

## One-line product

Turn video elements into reusable motion layers for editors and websites.

## Primary users

- short-form creators
- web designers
- ecommerce teams
- brand/social teams
- education video teams
- developer tools and creative apps

## First wedge

Website and short-form motion assets from creator-owned videos.

## MVP user story

As a creator or web designer, I can upload a short video, click an object, and receive a reusable web/video motion layer that I can edit, preview, and export.

## MVP requirements

### Upload

- Accept short video files.
- Validate duration, resolution, and size.
- Store source metadata.

### Object selection

- User can click a point or draw a box.
- Prompt is passed to a segmentation provider.

### Extraction

- Generate mask sequence.
- Generate cropped alpha/raster assets.
- Generate scene graph.
- Generate web manifest.
- Generate resource profile.

### Editing

- Move object.
- Scale object.
- Rotate object.
- Change opacity.
- Duplicate object.
- Toggle visibility.

### Preview

- Browser preview using cached assets.
- No AI rerun during normal transform edits.
- Show resource/performance profile.

### Export

- Website package.
- Transparent object export.
- Final video export.
- Developer JSON package.

## Non-goals for early MVP

- Perfect all-object scene decomposition.
- Hidden backside reconstruction.
- Full omnimatte shadows/reflections.
- Universal SVG/Lottie conversion.
- Marketplace before rights metadata exists.

## Product claim boundaries

Allowed claims:

```text
AI-assisted object extraction
cached object-layer editing
resource-aware preview
reusable motion layers
website-ready motion assets
```

Avoid claims:

```text
extract every object perfectly
convert any video to SVG
always smaller than video
automatic copyright-safe remixing
```
