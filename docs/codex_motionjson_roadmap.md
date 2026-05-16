# MotionJSON Roadmap for Codex Execution

## Roadmap policy

- Execute phases in order.
- Each phase ends with one git commit.
- Each phase writes `docs/roadmap/phase-N-report.md`.
- Each phase must preserve or document CLI behavior.
- Heavy ML providers must be optional and capability-gated.
- Reviewer subagent must inspect the diff before commit.

## Phase 0 — Repository discovery and guardrails

**Goal:** Understand the existing repository and install Codex-readable guardrails.

**Subagents:** `repo_archaeologist`, `product_strategist`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Map current packages, modules, CLI commands, extraction code path, test commands, examples, and docs.
- Identify where SAM2 provider is implemented and where raster fallback is triggered.
- Record current behavior for `extract`, `validate`, `correct`, `export`, and `backend` commands.
- Add repository `AGENTS.md` if not already present.
- Add `docs/roadmap/phase-0-report.md` with findings.

**Acceptance:**

- Current architecture map exists.
- Existing tests/smoke commands are documented.
- Known risky areas are listed.
- No product code changes except documentation/instructions unless necessary.

**Commit:** `phase 0: map repository and codex guardrails`

## Phase 1 — Typed project/run config foundation

**Goal:** Create a stable config/schema layer that both CLI and UI can use.

**Subagents:** `backend_cv_architect`, `repo_archaeologist`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Introduce typed run configuration models for video input, output, sampling, provider, prompts, detector settings, filters, export options, and debug flags.
- Add serialization/deserialization for project configs, e.g. `motionjson.project.json` and `run_config.json`.
- Add validation errors with user-friendly messages.
- Refactor CLI extraction to build this config without changing behavior.
- Add tests for config parsing and validation.

**Acceptance:**

- CLI command can produce/use the typed config internally.
- Invalid configs produce clear errors.
- Tests cover prompt point, prompt box, sampling, max frames, output mode, provider selection.

**Commit:** `phase 1: add typed extraction run configuration`

## Phase 2 — Provider capability registry and diagnostics

**Goal:** Make backend/model availability transparent before users run extraction.

**Subagents:** `backend_cv_architect`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`.

**Work:**

- Add provider registry for mask providers, detectors, trackers, vectorizers, and exporters.
- Add capability checks for Python package import, model availability, CUDA/CPU device, FFmpeg/video IO, output permissions, and optional extras.
- Add CLI diagnostics command or extend existing `backend` command.
- Add JSON-formatted diagnostics for the future UI.
- Add tests with mocked missing providers.

**Acceptance:**

- Users can run a command that reports available/unavailable providers and why.
- CUDA availability is not assumed.
- Missing optional dependencies do not break the base CLI.
- Diagnostics are machine-readable.

**Commit:** `phase 2: add provider capability diagnostics`

## Phase 3 — Job engine and artifact model

**Goal:** Support long-running extraction jobs with progress, logs, cancellation hooks, and artifacts.

**Subagents:** `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Add a local job model: queued, running, succeeded, failed, canceled.
- Create artifact directories per run with `run_config.json`, logs, metrics, previews, masks, MotionJSON output, and failure diagnostics.
- Implement progress events: video read, keyframe selection, candidate discovery, initial masks, propagation, track linking, vectorization, export.
- Add cancellation mechanism where feasible.
- Keep synchronous CLI behavior by wrapping job execution when needed.

**Acceptance:**

- A run produces a structured artifact directory.
- Failures include a readable error and raw traceback/log for advanced users.
- Job progress can be consumed by a UI/API later.
- Existing CLI outputs remain available.

**Commit:** `phase 3: add extraction job and artifact model`

## Phase 4 — Extraction provider abstraction refactor

**Goal:** Split the extraction pipeline into object discovery, mask generation, tracking, linking, vectorization, and export.

**Subagents:** `backend_cv_architect`, `repo_archaeologist`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Define interfaces/classes:
  - `ObjectCandidateProvider`
  - `MaskProvider`
  - `VideoTracker`
  - `TrackLinker`
  - `Vectorizer`
  - `Exporter`
- Move existing single SAM2 prompt flow into these abstractions.
- Add mock providers for tests and UI development.
- Add debug summaries showing what each stage produced.

**Acceptance:**

- Existing single-point/box extraction still works.
- Mock pipeline can produce deterministic tracks without ML dependencies.
- Pipeline stages can be tested independently.

**Commit:** `phase 4: refactor extraction into provider pipeline`

## Phase 5 — Multi-object candidate discovery modes

**Goal:** Implement the discovery approaches needed for “trace every object.”

**Subagents:** `backend_cv_architect`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`.

**Work:**

Add or scaffold capability-gated providers:

- `manual_prompt`: point/box/mask for one or more user-created objects.
- `sam_auto_masks`: automatic keyframe masks with area/stability/overlap filtering.
- `text_detector`: text-guided boxes/masks using a pluggable open-vocabulary detector.
- `class_detector`: optional known-class detector/segmenter/tracker path.
- `motion_foreground`: frame-difference/background-subtraction/optical-flow candidates.
- `external_masks`: import masks/boxes from files.

Each provider should expose:

- config schema;
- capability status;
- candidate output schema;
- debug artifacts;
- filter controls;
- test/mock mode.

**Acceptance:**

- At least two non-manual discovery modes are usable without GPU through mock/simple implementations.
- Provider outputs can feed the shared tracking/vectorization pipeline.
- UI-facing descriptions explain when to use each mode.

**Commit:** `phase 5: add multi-object discovery providers`

## Phase 6 — Track identity, filtering, dedupe, and raster fallback explanation

**Goal:** Prevent whole-frame/raster failures from being mysterious and manage object identities across methods.

**Subagents:** `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Add `ObjectTrack` model with ID, label, source, frames, masks/boxes/contours, confidence, warnings, and export status.
- Add candidate filtering: min/max area, max frame coverage ratio, duplicate IoU, background likelihood, minimum track length, confidence.
- Add deduplication and merge suggestions.
- Add raster fallback reason codes:
  - no candidates;
  - no masks accepted;
  - masks too large/whole-frame;
  - vectorization failed;
  - provider unavailable;
  - tracking failed;
  - user chose raster mode.
- Add summary metrics for each run.

**Acceptance:**

- Whole-frame masks can be detected and flagged.
- Raster fallback includes a reason code and suggested fixes.
- Multi-object outputs have stable IDs and labels.
- Tests cover filtering and fallback reasons.

**Commit:** `phase 6: add object tracks and fallback diagnostics`

## Phase 7 — Local API server and UI shell

**Goal:** Create the local-first UI foundation.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `release_packaging_engineer`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Add a local API server, preferably FastAPI if consistent with repo.
- Add endpoints for health, provider capabilities, projects, videos, run configs, jobs, progress, artifacts, and exports.
- Add React/TypeScript/Vite UI shell or the best repo-compatible equivalent.
- Add `motionjson ui` command to launch the server and UI.
- Add no-model/mock mode so UI can run on machines without GPU.

**Acceptance:**

- Local UI opens from a command.
- Health and capabilities are displayed.
- A project/video can be selected or created.
- Frontend builds in CI/smoke mode.

**Commit:** `phase 7: add local ui shell and api server`

## Phase 8 — Video viewer, prompt tools, and extraction wizard

**Goal:** Replace CLI copy/paste with a guided visual workflow.

**Subagents:** `frontend_ui_engineer`, `product_strategist`, `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Add video/frame viewer with canvas overlay.
- Add tools for point, box, mask brush, positive/negative point, object label, and keyframe selection.
- Add extraction wizard presets:
  - Trace one object.
  - Find objects from text.
  - Propose all visible segments.
  - Find moving objects.
  - Import external masks.
- Add advanced parameter panels for thresholds, keyframes, FPS, max frames, devices, model selection.
- Add config preview and save/load.

**Acceptance:**

- User can create a valid run config visually.
- UI warns when chosen provider is unavailable.
- Prompt coordinates are shown in video pixel coordinates.
- Generated config is accepted by backend validation.

**Commit:** `phase 8: add video prompt tools and extraction wizard`

## Phase 9 — Job run, progress, logs, and result review UI

**Goal:** Make extraction runs visible and debuggable.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Start jobs from UI.
- Show progress by pipeline stage.
- Stream logs or poll job events.
- Display artifact list.
- Show preview masks/tracks over video frames.
- Add track list with visibility, label, source, confidence, frame coverage, warnings, and export inclusion.
- Show raster fallback diagnostics if relevant.

**Acceptance:**

- UI can run a mock extraction job end-to-end.
- UI can display at least one real or mock object track.
- Logs and artifacts are accessible.
- Failed runs show actionable messages.

**Commit:** `phase 9: add ui job execution and result review`

## Phase 10 — Correction tools and partial reruns

**Goal:** Let users fix automated mistakes.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Delete/hide/relabel tracks.
- Merge duplicate tracks.
- Split a track by frame range or identity break.
- Add a missing object from a point/box/mask on a selected frame.
- Repair a track over a frame range using additional prompts.
- Store correction history in the project.
- Implement partial rerun hooks where feasible.

**Acceptance:**

- Corrections update project state and export inclusion.
- Corrections survive reload.
- Partial rerun or repair path is documented even if only mock/simple at first.
- Tests cover track edit operations.

**Commit:** `phase 10: add track correction workflows`

## Phase 11 — Export, validation, and interoperability

**Goal:** Make outputs trustworthy and useful beyond the app.

**Subagents:** `backend_cv_architect`, `frontend_ui_engineer`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`.

**Work:**

- Export MotionJSON from edited project state.
- Validate MotionJSON against schema.
- Export preview video with overlays.
- Export masks/contours/boxes per object as optional artifacts.
- Add export presets: compact, debug, vector-heavy, raster fallback.
- Add import of previous MotionJSON result for review.
- Preserve CLI export behavior or document migration.

**Acceptance:**

- UI can export MotionJSON and validate it.
- Preview video or frame overlays can be generated.
- Existing CLI export tests pass.
- Export includes provenance/config metadata.

**Commit:** `phase 11: add validated export workflows`

## Phase 12 — Evaluation suite and benchmark fixtures

**Goal:** Prevent regressions and make extraction quality measurable.

**Subagents:** `qa_benchmark_engineer`, `backend_cv_architect`, `docs_devrel_engineer`, `reviewer`.

**Work:**

- Add synthetic fixture generator for simple shapes: red ball, multiple moving objects, occlusion, small object, camera motion.
- Add expected outputs or tolerance-based checks for mock/simple providers.
- Add benchmark command to compare modes.
- Add metrics: object count, coverage, mask area ratio, continuity, duplicate overlap, runtime.
- Add regression tests for whole-frame mask rejection and raster fallback reason codes.

**Acceptance:**

- Benchmarks run without GPU.
- CI can run lightweight fixtures.
- Reports are human-readable and machine-readable.
- Known demo videos have documented expected behavior.

**Commit:** `phase 12: add evaluation fixtures and benchmarks`

## Phase 13 — Packaging, first-run setup, and adoption docs

**Goal:** Make it easy for users to install, launch, and succeed.

**Subagents:** `release_packaging_engineer`, `docs_devrel_engineer`, `frontend_ui_engineer`, `qa_benchmark_engineer`, `reviewer`.

**Work:**

- Add dependency extras: `ui`, `sam2`, `detectors`, `yolo`, `dev`, etc.
- Add first-run setup wizard or diagnostics screen.
- Add Windows PowerShell-safe examples.
- Add sample projects and tutorials.
- Add docs for each extraction mode with “when to use this” and “failure modes.”
- Add launcher scripts if appropriate.

**Acceptance:**

- User can run documented install and launch commands.
- Missing models/dependencies are explained.
- Docs cover red-ball demo and multi-object demo.
- Package metadata includes UI extras.

**Commit:** `phase 13: add packaging and onboarding docs`

## Phase 14 — Polish, accessibility, performance, and release candidate

**Goal:** Prepare a release-quality cut.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `release_packaging_engineer`, `reviewer`.

**Work:**

- UI polish: layout, keyboard shortcuts, tooltips, responsive panels, empty states.
- Accessibility: labels, contrast, focus handling, keyboard navigation.
- Performance: frame cache, mask preview optimization, job cancellation, memory checks.
- Security/privacy: local-only defaults, no unexpected network calls, safe artifact paths.
- Release notes and migration guide.
- Final smoke: CLI, UI, mock extraction, sample video, export validation.

**Acceptance:**

- All supported tests pass.
- User can complete at least one end-to-end UI workflow.
- Release notes exist.
- Known limitations are documented.

**Commit:** `phase 14: prepare ui multi-object tracing release candidate`

## Future roadmap after release candidate

- Tauri/Electron desktop wrapper.
- Collaboration/shared review exports.
- More detectors and model plugins.
- Active labeling and fine-tuning workflows.
- Batch processing UI.
- Dataset import/export.
- Advanced rotoscoping/keyframe interpolation.
- Cloud/offline hybrid processing as optional integration.
