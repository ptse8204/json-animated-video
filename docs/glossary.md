# Glossary

Short practical definitions for terms used throughout MotionJSON docs.

## Object Layer

A reusable visual layer extracted from a source video object. It usually
contains cached raster/alpha media plus JSON timing, transform, identity,
visibility, rights, and export metadata.

## Mask

A per-frame black-and-white image that marks which pixels belong to an object.
White pixels are included; black pixels are background. Masks can come from
thresholding, motion foreground, external files, SAM2, or other providers.

## Track

A temporally linked object identity across frames. A track can include labels,
visibility, frame coverage, boxes, centroids, masks, confidence, warnings,
source provider, and export status.

## Scene Graph

The JSON structure that describes objects, layers, timing, transforms, assets,
rights metadata, provider performance, and playback/export state. Use
`scene_graph.json` or `web_asset_manifest.json` for runtime playback.

## Manifest

A JSON file that summarizes a piece of output. Examples include
`web_asset_manifest.json`, `rights_manifest.json`, object manifests, export
manifests, and correction manifests.

## Provider

A modular component that performs one pipeline step, such as discovery,
masking, tracking, linking, vectorizing, or exporting. Providers must report
capability status instead of silently failing.

## Discovery Provider

A provider that proposes object candidates before mask tracking. Examples are
manual prompts, motion foreground, external masks, text detectors, class
detectors, and automatic segment proposals.

## Mask Provider

A provider that produces masks for one object or candidate. Examples are
`threshold`, `motion`, `external`, `mock`, `sam2-local`, and `sam2-hosted`.

## Raster/Alpha

Image or video pixels with transparency. Photoreal objects usually remain
raster/alpha assets because texture, blur, shadows, hair, and reflections do not
convert cleanly to SVG or Lottie.

## Raster-Only Fallback

An explicit fallback state where object/vector tracks are unavailable,
rejected, or intentionally bypassed, so the output cannot represent separate
object layers. Read `fallback_diagnostics.json` and `tracks.json` before
treating this as a successful object extraction.

## Vector Overlay

An auxiliary vector representation, such as contours, boxes, labels, simple
silhouettes, or annotations. It can help with review or lightweight graphics,
but it is not a guarantee that photoreal footage became clean SVG/Lottie.

## SAM2

Segment Anything Model 2 style promptable segmentation/tracking. SAM2 can track
an object after a prompt, but it is not automatic semantic discovery by itself.
Text-guided workflows need detector candidates before segmentation/tracking.

## Detector

A provider that turns text labels or known classes into boxes or candidates.
Detector output can then feed mask providers or trackers.

## Capability Diagnostics

Structured CLI/UI status that reports whether providers are ready, CPU-only,
missing optional dependencies, missing model files, not configured, or
unavailable. Diagnostics should mention missing CUDA, SAM2, detectors, FFmpeg,
model paths, hosted endpoints, and credentials when relevant.

## Correction

A review-time edit to a track or mask, such as relabeling, hiding, deleting,
merging, splitting, adding an object, or recording a repair request. Current
local correction paths are deterministic and should not pretend optional ML
providers ran.

## Export Preset

A named handoff profile such as `compact`, `debug`, `vector-heavy`, or
`raster-fallback`. Presets decide which reviewed tracks, masks, contours,
previews, and diagnostics are packaged.
