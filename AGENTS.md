# AGENTS.md — MotionJSON Engineering Instructions for Codex

## Project mission

MotionJSON should become a local-first video object tracing application. It must support both expert CLI use and approachable UI-driven workflows for users who want to trace one object, trace many objects, or inspect/correct extraction results.

The immediate user pain is that a single SAM2 point prompt can fail badly and export the whole video as a raster layer. The software should guide users toward the right workflow, surface backend/model failures clearly, and provide review/correction tools before export.

## Non-negotiable rules

- Work phase-by-phase. Do not jump ahead to later phases unless the current phase acceptance criteria are complete.
- End every phase with a git commit.
- Do not hide or silently swallow provider failures. If CUDA, SAM2, detectors, FFmpeg, model weights, or optional dependencies are unavailable, show this in diagnostics and logs.
- Preserve CLI compatibility unless a phase explicitly migrates an interface with documentation and tests.
- Prefer small stable abstractions over one-off UI glue.
- Keep heavyweight ML dependencies optional and capability-gated.
- Do not make the default install impossible for CPU-only or non-ML users.
- Public APIs, CLI flags, project config, and MotionJSON schema changes must be documented.
- Add tests for every behavior change that can be tested without GPU.
- Provide CPU/mock/no-model paths for tests and UI smoke checks.
- When an extraction produces raster-only output, the UI and logs must explain why vector/object tracks were unavailable.

## Phase commit protocol

For each phase:

1. Start from a clean working tree or record why it is not clean.
2. Read the phase requirements in `docs/codex_motionjson_roadmap.md` and `codex_tasks.yaml`.
3. Spawn/assign subagents for exploration, implementation, UI, tests, docs, and review as appropriate.
4. Implement the smallest coherent slice that satisfies the phase.
5. Run relevant tests and smoke commands.
6. Write `docs/roadmap/phase-N-report.md` with:
   - summary;
   - changed files;
   - tests run;
   - known limitations;
   - follow-up tasks.
7. Commit with `git commit -m "phase N: <description>"`.

## Suggested test commands

Codex must inspect the repository before assuming exact commands. When available, prefer:

```bash
python -m pytest
python -m motionjson.cli --help
python -m motionjson.cli extract --help
python -m motionjson.cli backend --help
```

For frontend phases, inspect package manager files and run the matching commands, for example:

```bash
npm test
npm run lint
npm run build
```

If a command is unavailable, document that in the phase report rather than pretending it passed.

## Architecture preferences

- Python remains the extraction/runtime backend.
- Add a local web UI, ideally FastAPI + React/TypeScript/Vite, unless repository constraints strongly suggest another stack.
- Provide `motionjson ui` or `python -m motionjson.cli ui` to launch the local app.
- Use a job system for extraction runs; do not block the UI while models run.
- Store projects and artifacts locally. Avoid cloud assumptions.
- Use Pydantic or equivalent validation for run configs and API payloads.
- Keep provider interfaces modular:
  - `ObjectCandidateProvider`
  - `MaskProvider`
  - `VideoTracker`
  - `TrackLinker`
  - `Vectorizer`
  - `Exporter`

## UI principles

- The UI must help users choose the correct approach instead of forcing them to know CLI flags.
- Use a goal-first workflow: “Trace one object,” “Find objects from text,” “Find moving objects,” “Propose all visible segments,” “Review existing result.”
- Always show backend capability status before a run.
- Allow manual correction after automated extraction.
- Show object tracks as first-class entities: name, color, visibility, confidence, frame coverage, source provider, and export status.
- Include preview artifacts and debug overlays.
- Avoid jargon where possible; include advanced controls in expandable panels.

## ML/provider rules

- SAM2 is promptable segmentation/tracking, not automatic semantic discovery by itself.
- “Trace every object” must be implemented as a product workflow that chooses one or more discovery providers, then segments/tracks object candidates.
- Text prompts should be interpreted by a detector/open-vocabulary candidate provider, not by raw SAM2.
- Automatic masks must be filtered to avoid exporting floor/wall/background fragments as user-facing objects unless the user explicitly chooses “all visible segments.”
- Include model/device diagnostics and a mock provider for UI/test runs.

## Documentation expectations

Every user-facing capability needs:

- CLI help or UI tooltip text;
- a docs page or section;
- a minimal example;
- error/failure guidance.

## Review posture

Review like an owner. Prioritize:

- correctness;
- reproducibility;
- clear errors;
- GPU/CPU dependency safety;
- UI state consistency;
- testability;
- preserving existing behavior.

Avoid broad rewrites unless the phase explicitly requires one.
