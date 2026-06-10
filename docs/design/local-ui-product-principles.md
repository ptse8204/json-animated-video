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

- Start with the guided first-run flow. Model setup must show one recommended
  SAM provider for the selected workflow, what setup is missing, and whether
  the next action is local install/cache/check/smoke or hosted API linking.
- Keep debug mock mode contributor-only. It must be launched explicitly with
  `--debug-mock` and must never make unavailable SAM/CUDA/provider paths look
  ready.
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

- A redesign may change the shell, navigation, cards, right rails, steppers,
  dashboards, and panel layout.
- Preserve source identity, goal clarity, provider readiness, hosted-call
  consent, run progress, failure recovery, review truth, export readiness, and
  rights visibility.
- Keep the normal path readable before exposing advanced diagnostics, raw JSON,
  logs, routes, or artifacts.
- Layout must avoid horizontal scrolling, overlapping controls, hidden primary
  actions, and clipped status/error text at supported viewports.
- Use `docs/product/ui_redesign_brief.md` as the current redesign brief.

## State Rules

- Empty states should explain the next local action.
- Loading states should identify the local backend action.
- Errors should say whether the issue is local setup, provider readiness,
  missing credentials, bad inputs, or unavailable artifacts.
- Hosted/network provider warnings must include cost and privacy language before
  a run starts.
- Raster-only or vector-unavailable output must show the reason and suggested
  fixes.
