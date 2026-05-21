# AGENTS.md — MotionJSON Engineering Instructions for Codex

## Project mission

MotionJSON should become a local-first video object tracing application. It must support both expert CLI use and approachable UI-driven workflows for users who want to trace one object, trace many objects, or inspect/correct extraction results.

The immediate user pain is that a single SAM2 point prompt can fail badly and export the whole video as a raster layer. The software should guide users toward the right workflow, surface backend/model failures clearly, and provide review/correction tools before export.

## Non-negotiable rules

- Work phase-by-phase. Do not jump ahead to later phases unless the current phase acceptance criteria are complete.
- End every phase with a git commit.
- Use `docs/roadmap/ui_model_connector_plan.md` as the active roadmap when the
  work concerns the nontechnical Local UI, model-assisted planning, provider
  setup, guided review, export handoff, or Codex operational integration.
  Older numeric, public-onboarding, commercial, and OD roadmaps are historical
  context unless a user explicitly selects one of those tracks.
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
2. Read the active phase requirements in `docs/roadmap/ui_model_connector_plan.md`, `docs/codex_motionjson_roadmap.md`, and `codex_tasks.yaml`.
   For UI/model roadmap phases, also use
   `docs/codex/ui_model_operational_prompts.md` for Codex prompt templates,
   scout prompts, and review-only operating guardrails.
3. The master Codex agent owns planning, implementation, validation, review synthesis, and commits. Use bounded read-only scouts only when independent critique materially improves quality.
4. Implement the smallest coherent slice that satisfies the phase.
5. Run relevant tests and smoke commands.
6. Write `docs/roadmap/phase-N-report.md` with:
   - summary;
   - changed files;
   - tests run;
   - known limitations;
   - follow-up tasks.
7. Commit with `git commit -m "phase N: <description>"`.

## Scout workflow

Use scouts sparingly and keep them read-only unless a user explicitly assigns
implementation work. Suitable scouts for the active UI/model roadmap are:

- `plan-risk-scout`: critiques phase plans and API shapes before implementation.
- `diff-review-scout`: reviews final diffs for correctness, secrets, and regressions.
- `rendering-scout`: reviews browser screenshots, layout behavior, and visual regressions.
- `test-gap-scout`: checks whether tests cover behavior, edge cases, and regressions.
- `adoption-scout`: checks whether the feature helps less technical users.

Every scout must return only:

- Scope inspected
- Files/symbols reviewed
- Findings
- Evidence
- Recommended action
- Confidence level

Use at most one or two scouts per phase unless the user explicitly asks for
more. The master agent makes the final decision and is responsible for the
commit.

When a scout is used, prefer the matching prompt template in
`docs/codex/ui_model_operational_prompts.md`. Scouts must remain read-only by
default: they may inspect files, screenshots, diffs, tests, and validation
output, but they may not edit files, install dependencies, change provider
settings, commit, push, publish packages, or spawn other agents unless the user
explicitly changes that scope.

Do not add Codex or GitHub automation that can push commits, publish packages,
mutate provider settings, or call hosted providers without human review.

## Browser evidence for UI phases

Any phase that changes Local UI layout, cards, fonts, visual hierarchy, panels,
tool layout, right rail, wizard layout, provider settings, review cards, export
cards, or responsive behavior must use rendered browser evidence.

Required workflow:

1. Start the Local UI in mock/no-model mode.
2. Open it with the Codex in-app browser when available, otherwise use the
   repository headless Chrome/layout tooling.
3. Capture before screenshots before layout changes.
4. Inspect those screenshots before coding.
5. Capture after screenshots.
6. Compare before/after evidence in the phase report.
7. Save screenshots under `docs/design/screenshots/<phase-id>/` unless the
   phase report explains why generated screenshots should not be committed.

Required viewports for layout phases are 390x844, 768x1024, 1024x768,
1366x768, 1440x900, and 1920x1080 where tooling supports them.

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
