---
historical: true
default_context: false
---

# Phase OD-00 Report: API-First Object Discovery Architecture Audit

## Summary

Phase OD-00 re-checked the repository state before implementing the API-first
object discovery roadmap. The current codebase already has typed run configs,
provider diagnostics, discovery-provider scaffolds, local UI API routes,
authenticated backend API routes, worker execution, artifact registration,
review aggregation, correction history, and UI candidate/track review panels.

The normal completed-job review path is mostly API/artifact-backed today:
`candidates.json` is registered as `candidate_summary`, `tracks.json` is
registered as `track_summary`, and the local UI review route aggregates those
artifacts into `/api/jobs/{jobId}/review`.

The main API-first boundary gap is frontend preview fallback logic. The local
UI still synthesizes temporary config-derived tracks while a job is pending or
while artifact-backed review data is unavailable. That logic is useful for
draft UI state, but OD-05 must make it explicitly demo/pending-only and
non-exportable for normal completed jobs.

## Starting Working Tree

The working tree was not clean before this phase. Existing untracked files were
present and were treated as user-provided prompt/context files, not phase
outputs:

- `docs/codex/motionjson_codex_prompt_api_first_object_discovery_sam2_sam3.md`
- `docs/codex/motionjson_sam2_sam3_decision_notes.md`

## Architecture Findings

### Repository Docs And Index

- `README.md` and `docs/index.md` already document the no-model local UI path,
  provider diagnostics, SAM2 limitations, optional hosted providers, runtime
  packages, screenshots, troubleshooting, and release-candidate boundaries.
- `docs/local_ui.md` lists the local UI API routes for capabilities, provider
  settings, run config validation, jobs, review, artifacts, corrections,
  exports, and library workflows.
- `docs/discovery_providers.md` documents the existing discovery modes:
  `manual_prompt`, `motion_foreground`, `external_masks`, `sam_auto_masks`,
  `text_detector`, and `class_detector`.
- `docs/provider_capabilities.md` documents capability status fields,
  provider names, missing-dependency behavior, no-model providers, and
  hosted-provider opt-in expectations.
- `docs/security/api_keys.md` documents local provider settings, redaction,
  environment-variable precedence, and no-network provider setup tests.

### Typed Config And Validation

- `src/motionjson/config.py` owns the typed `ExtractionRunConfig` model.
- Current discovery modes are limited to `manual_prompt`, `sam_auto_masks`,
  `text_detector`, `class_detector`, `motion_foreground`, and
  `external_masks`.
- `auto_object_proposals`, `qualityPreset`, clean/balanced/maximum-recall
  defaults, trace-everything acknowledgement, and selected-only tracking
  defaults are not implemented yet.
- `POST /api/run-config/validate` in `src/motionjson/ui/server.py` normalizes
  frontend payloads through `ExtractionRunConfig` and returns validation
  errors/warnings.

### Provider Settings And Capability Diagnostics

- `src/motionjson/provider_settings.py` defines local provider settings for
  `mock`, `threshold`, `motion`, `external`, `sam2-local`, `sam2-hosted`,
  `openrouter`, `text_detector`, and `class_detector`.
- `src/motionjson/capabilities.py` reports no-model providers, SAM2 local and
  hosted readiness, detector readiness, FFmpeg status, CUDA status, model path
  checks, credential presence, and hosted network opt-in state.
- Mock discovery readiness is not cleanly separated from real provider
  readiness yet: the worker can run some discovery modes in mock mode, while
  capability/provider-settings records still mark the real providers as
  unavailable, non-runnable, or not implemented.
- SAM3 provider IDs and diagnostics are not present yet.

### Discovery Providers And Worker Execution

- `src/motionjson/providers/discovery.py` contains the current discovery
  provider schemas and mock/scaffold implementations.
- `sam_auto_masks`, `text_detector`, and `class_detector` can run in mock mode
  and write mask handoff directories for the shared pipeline.
- `src/motionjson/backend/worker.py` routes local UI jobs through discovery
  providers for `text_detector`, `sam_auto_masks`, `class_detector`, and
  `motion_foreground`.
- Real `sam_auto_masks` still requires an injected/configured backend and is
  capability-gated.

### Review Payloads And Artifacts

- `src/motionjson/pipeline.py` writes `candidates.json`, `tracks.json`,
  `fallback_diagnostics.json`, scene graph, resource profile, masks, cutouts,
  and preview artifacts.
- `src/motionjson/job_artifacts.py` maps `candidates.json` to
  `candidate_summary` and `tracks.json` to `track_summary`.
- `src/motionjson/ui/server.py` builds `/api/jobs/{jobId}/review` from
  registered artifacts and correction history, redacting storage keys and
  sensitive values.
- Current candidate records expose `id`, `label`, `source`, `frameIndex`,
  geometry, score, z-index, and metadata. The OD-02 shared shape fields such as
  `candidateId`, `thumbnailArtifactId`, `maskPreviewArtifactId`, `areaRatio`,
  `stabilityScore`, `motionScore`, `confidence`, `reviewStatus`, rejection
  counts, and default selection are not present yet.

### Authenticated Backend API

- `src/motionjson/backend/api.py` exposes dependency-light authenticated
  `/v1` routes for projects, assets, extraction jobs, job events/artifacts,
  corrections, track edits, asset packages, renders, webhooks, support, beta,
  billing, and library workflows.
- It has `/v1/jobs/{jobId}/track-edits` but no OD-04 equivalent
  `/v1/extraction-runs/{runId}/track-selected` route yet.
- Authenticated extraction currently queues deterministic local extraction
  through existing provider policy and does not accept the full OD discovery
  candidate-selection flow yet.
- The authenticated API does not yet have local UI parity for review
  aggregation, candidate selection, discovery capability surfacing, or full
  run-config validation.

### Frontend API Boundary And Synthetic Fallbacks

- `src/motionjson/ui/static/app.js` renders `state.jobReview?.candidateSummary`
  and `review.tracks` returned by the local UI API when present.
- `buildReviewTracks()` uses API review tracks first, then job result tracks,
  then temporary synthetic/config-derived tracks only when the job is not in a
  terminal state and no vector-unavailable review exists.
- `configReviewTracks()` creates prompt/config-estimated tracks for pending UI
  preview. `syntheticTracks` also appears in correction-state handling for
  local add/split pending edits.
- OD-05 should isolate these paths as demo/pending-only with explicit metadata
  such as `demoMode: true`, `source: "demo-only"`, and `exportable: false`,
  and prevent them from appearing as normal completed-job outputs.

### Export Review Gates

- Current export workflows derive inclusion from scene objects and correction
  state. They do not yet require user review/selection for auto-discovered
  candidates.
- Later phases must ensure automatically discovered objects cannot become
  normal exportable tracks until the API records candidate review state.

## Changed Files

- `docs/roadmap/phase-od-00-report.md`
- `docs/repo_status.md`

## Tests And Validation Run

- `python3 -m motionjson.cli --help` passed.
- `python3 -m motionjson.cli ui --help` passed.
- `python3 -m motionjson.cli extract --help` passed.
- `python3 -m motionjson.cli backend --help` passed.
- `python3 -m motionjson.cli benchmark --help` passed.
- `python3 -m pytest -q` passed: 306 tests.
- `npm test` passed: 19 tests.
- `npm run lint` passed.
- `npm run build` passed.

## Known Limitations

- `auto_object_proposals` is not yet a valid discovery mode.
- Object discovery quality presets are not represented in typed config yet.
- Candidate review payloads are still `candidates.json` summaries rather than
  the OD shared review schema.
- Selected-candidate tracking API routes do not exist yet.
- Authenticated `/v1` routes do not yet expose review aggregation or selected
  candidate tracking parity with the local UI.
- Provider capability payloads do not yet distinguish mock-runnable discovery
  from real provider readiness.
- Auto-discovered candidate exports are not yet blocked on explicit candidate
  review.
- The UI candidate panel is read-only and summary-oriented; it does not support
  keep/ignore selection and Track selected yet.
- SAM2 automatic proposal support is mock/scaffold-only unless an injected
  backend is provided.
- SAM3 provider diagnostics, mock modes, local adapters, and hosted adapters
  are not present yet.
- Trace Everything is not implemented as an explicit expert mode.

## Follow-Up Tasks

- OD-01: add API-addressable discovery presets to typed config.
- OD-02: extend candidate review payloads and summaries so the UI can render
  API-owned candidates without inventing fields.
- OD-03: add deterministic mock `auto_object_proposals` artifacts.
- OD-04: add selected-candidate tracking routes to local UI and authenticated
  APIs.
- OD-05: make normal completed-job UI review render API candidates/tracks only
  and mark any retained synthetic preview state as demo/pending-only and
  non-exportable.
