# Product Plan: AI-Assisted Object-Layer Video Editing

## Product thesis

The goal is to help editors work faster, use less rendering resource, and get better previews with AI assistance. The product should not convert whole videos into JSON. It should convert selected video elements into editable object layers.

The winning representation is a hybrid:

- original video remains compressed video
- AI extracts selected object masks/tracks once
- real footage becomes raster/alpha assets
- simple graphics become vector/Lottie/SVG assets
- JSON stores object identity, timing, transforms, masks, z-order, interactions, and rights metadata
- Canvas/WebGL/PixiJS renders fast previews
- Remotion/FFmpeg/WebCodecs handles final output

## MVP wedge

Start with short-form creator and web-editor workflows:

1. User uploads a 3-10 second clip.
2. User clicks an object.
3. System tracks the object mask across the clip.
4. System generates a reusable transparent motion layer.
5. User edits the layer using normal transform controls.
6. The editor previews through a JSON scene graph instead of repeatedly recomputing the whole effect.
7. Export to MP4/WebM plus optional object-motion package.

## Why this improves speed and resource use

AI runs at ingest or correction time, not continuously.

After extraction, edits become lightweight scene-graph changes:

- move object -> change JSON x/y
- resize object -> change JSON scale
- hide object -> change JSON opacity/visibility
- reuse object -> reference cached asset
- replace background -> composite cached object layer over a new background
- add outline/label -> draw vector overlay from mask-derived geometry

## Differentiation

Existing tools can cut objects, remove backgrounds, or convert video to Lottie. The opportunity is to combine:

- AI object identity and tracking
- reusable object assets, not just one-off edits
- JSON edit graph and portable asset package
- fast preview renderer
- quality router: vector vs raster vs normal video
- creator licensing/attribution metadata
- integrations into existing editor workflows

## Technical phases

### Phase 0: Baseline prototype

- External mask sequence input.
- Cutout PNG sequence export.
- JSON motion graph.
- Resource profile report.
- Canvas preview.
- Optional silhouette Lottie for simple vector-like objects.

### Phase 1: Hosted neural segmentation

- SAM 2 or similar video segmentation API integration.
- Click prompts and correction prompts.
- Mask normalization.
- Object QA score: stability, drift, edge roughness, missing frames, occlusion risk.
- Auto-route to raster+JSON, vector+JSON, or normal video fallback.

### Phase 2: Fast browser editor

- Web timeline.
- Object picker.
- Drag/drop transform editing.
- Cached object-layer preview.
- Template-based remixing.
- Export via FFmpeg/Remotion/WebCodecs.

### Phase 3: Production optimization

- Pack cutouts into WebP/AVIF sprite atlases or transparent WebM.
- Use PixiJS/WebGL for preview rendering.
- GPU texture caching.
- Incremental re-rendering: only changed layers invalidate.
- Batch inference and cache segmentation outputs.
- Self-host segmentation when volume justifies it.

### Phase 4: Advanced quality moat

- Temporal mask smoothing.
- Detail-preserving alpha matting.
- Motion-blur-aware cutouts.
- Inpainting clean plates.
- Shadow/reflection handling.
- Color/lighting matching.
- Loop maker for motion stickers.

## Commercial risks

- Generic AI cutout is already a feature in large editing platforms.
- Pure video-to-Lottie is too narrow and may produce poor quality for real footage.
- Rights and likeness issues are serious for grabbing elements from arbitrary online videos.
- Editors will not adopt the system unless it exports into existing workflows.

## Commercial moat candidates

- Object-motion package format that works across editors.
- Fast WebGL editing preview for cached video objects.
- High-quality mask stability and edge refinement.
- Rights-aware remix marketplace.
- API for web editors and template systems.
- Integrations with Premiere, After Effects, CapCut-like editors, Canva-like editors, Remotion, and Lottie/dotLottie workflows.
