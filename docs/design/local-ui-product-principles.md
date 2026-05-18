# Local UI Product Principles

MotionJSON is a local-first object-layer editing tool. The Local UI should make
one safe path obvious before it exposes expert controls.

## Primary Users

- Creators and editors who want to cut one object from a clip and reuse it.
- Web developers who need a web-friendly motion layer or manifest.
- Motion designers who need review, correction, and export confidence.
- ML/CV experimenters who need provider diagnostics and artifacts.
- Future commercial/team users who need project history, provider cost signals,
  rights reminders, and predictable export handoff.

## Product Rules

- Start with mock/no-model mode. It must be clear that no GPU, SAM2, detector,
  model weights, or cloud key is required for the first run.
- Keep provider/model failures visible. Do not hide CUDA, FFmpeg, SAM2, detector,
  model-weight, or hosted-provider diagnostics.
- Show workflow before parameters. Users should see the project/video/provider/
  run/review/export path before advanced knobs.
- Treat tracks as first-class review items: name, visibility, confidence,
  provider/source, warnings, and export state.
- Keep advanced JSON, logs, routes, and artifacts available through progressive
  disclosure.
- Do not force users to read CLI flags before they can run the guided path.

## Layout Rules

- The desktop shell uses stable regions: left goal rail, main workspace, right
  inspector.
- Main workspace owns the video viewer, project/video setup, extraction settings,
  and run preview.
- Right inspector owns run monitor, review, artifacts/export, corrections,
  library, and route diagnostics.
- At 1024px and below, the inspector moves below the workspace and the content
  becomes one column.
- Panels must not require horizontal scrolling at 1366x768, 1440x900,
  1920x1080, or 1024x768.

## State Rules

- Empty states should explain the next local action.
- Loading states should identify the local backend action.
- Errors should say whether the issue is local setup, provider readiness,
  missing credentials, bad inputs, or unavailable artifacts.
- Hosted/network provider warnings must include cost and privacy language before
  a run starts.
- Raster-only or vector-unavailable output must show the reason and suggested
  fixes.
