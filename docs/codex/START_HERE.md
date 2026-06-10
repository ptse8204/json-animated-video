# Codex Start Here

MotionJSON is a local-first video object tracing application. It supports expert CLI workflows and a nontechnical Local UI for choosing a tracing goal, checking provider readiness, running extraction, reviewing results, correcting failures, and exporting MotionJSON assets.

## Current Truth

- MotionJSON is local-first by default.
- Current UI is dependency-light/static unless a task explicitly changes architecture.
- Local backend uses SQLite and filesystem storage.
- Python backend/CLI and JS runtime/SDK both exist.
- Python source lives under `src/motionjson/`.
- Static UI assets live under `src/motionjson/ui/static/`.
- JS packages live under `packages/motionjson-runtime/` and `packages/motionjson-sdk/`.
- Optional SAM2/SAM3/detector/hosted providers are capability-gated.
- OpenAI/OpenRouter are planning/reasoning only, not segmentation providers.
- CPU/mock/no-model flows must remain usable for tests and smoke checks.
- Historical docs are not default context.

## Default Read Protocol

Default Codex context is only:

1. `docs/codex/START_HERE.md`
2. `docs/codex/CURRENT_TASK.md`
3. `docs/codex/SAFETY_INVARIANTS.md`
4. `docs/codex/CURRENT_ARCHITECTURE.md`
5. `docs/codex/CONTEXT_MANIFEST.yaml`

Do not broaden the read set until the task route is clear.

## Routing Rule

Use `docs/codex/CONTEXT_MANIFEST.yaml` to choose extra docs, source paths, and tests for the specific subsystem. Read only the route needed for the task.

No broad root-doc scan by default. Do not load every README, roadmap, phase report, design note, or archived planning packet just because it exists.

## Archive Rule

Do not read `docs/archive/`, archived prompt packets, completed phase reports, old root docs, old future plans, or historical roadmap material unless the user explicitly asks for historical analysis or the manifest route says an archive index is needed.

Archived material is evidence, not current instruction.

## Source-Code-Is-Truth Rule

When docs and code disagree, inspect source and tests. Prefer current code paths, current CLI help, current package metadata, and passing tests over stale documentation. Update docs when a task changes public behavior, CLI flags, schemas, safety rules, or user-facing workflows.

## Doc Budget

Keep default Codex context below 1,500 lines and 60,000 characters. If this budget is exceeded, shrink docs or split task-specific reference material out of the default read set.

Use:

```bash
python3 scripts/check_codex_context_budget.py
```

## Safety Summary

- No hosted calls without explicit user opt-in.
- No browser-side secrets.
- Keep provider failures visible in diagnostics, logs, UI, and validation output.
- Heavy ML dependencies stay optional.
- Model planners produce proposals only; extraction must use explicit CV providers.
- Review and export gates must remain truthful.
- Raster-only output must explain why vector/object tracks were unavailable.
- Do not overclaim clean SVG/Lottie/vector conversion from photoreal video.

## Working Pattern

1. Read the default Codex docs.
2. Select one manifest route.
3. Inspect the listed source paths and tests.
4. Implement the smallest coherent change.
5. Run relevant validation.
6. Write or update the phase/task report when required.
7. Commit at phase completion when the task asks for phase protocol.
