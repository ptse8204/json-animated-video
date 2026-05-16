# Codex Master Prompt — MotionJSON UI + Multi-Object Extraction Roadmap

You are the Master Agent for the `motionjson` repository.

Read these files first:

- `AGENTS.md`
- `docs/codex_motionjson_context.md`
- `docs/codex_motionjson_prd.md`
- `docs/codex_motionjson_roadmap.md`
- `docs/codex_motionjson_architecture.md`
- `docs/codex_motionjson_ui_spec.md`
- `docs/codex_motionjson_ml_pipeline_spec.md`
- `docs/codex_motionjson_quality_benchmarks.md`
- `codex_tasks.yaml`

## Mission

Transform MotionJSON from a mostly CLI-driven extractor into a local-first application that helps users trace video objects with multiple extraction approaches:

1. single-object prompt tracking;
2. text-guided object discovery + SAM2 segmentation/tracking;
3. automatic mask proposals + filtering/tracking;
4. optional detector/segmenter based discovery/tracking;
5. motion-only discovery;
6. review/correction/export workflows.

The UI must stop users from “goofying in CLI copy/paste” and make the pipeline understandable, debuggable, and adoptable.

## Required subagent workflow

Use a master-agent / subagent pattern. Spawn specialized subagents when phases involve their domain, wait for their results, consolidate, and only then implement or commit.

Use these project-scoped custom agents if available:

- `repo_archaeologist`: map current repo structure, existing CLI, backend, tests, and packaging.
- `product_strategist`: refine user flows, acceptance criteria, and naming.
- `backend_cv_architect`: design/implement provider abstractions and CV/ML pipelines.
- `frontend_ui_engineer`: design/implement UI, API integration, state management, and browser smoke checks.
- `qa_benchmark_engineer`: implement tests, fixture videos, mock providers, benchmarks, and regression checks.
- `docs_devrel_engineer`: write docs, examples, onboarding, and troubleshooting.
- `release_packaging_engineer`: implement launchers, dependency groups, packaging, and installer/readiness checks.
- `reviewer`: review correctness, risks, missing tests, and phase acceptance before commits.

If custom agents are unavailable, spawn built-in `explorer`/`worker`/`reviewer` style agents with the same roles.

## Mandatory phase loop

For each phase in `codex_tasks.yaml`:

1. Announce the phase objective.
2. Spawn relevant subagents to inspect or design the phase.
3. Consolidate their findings into a concrete implementation plan.
4. Implement the phase.
5. Run the phase’s required tests and smoke commands.
6. Spawn `reviewer` to inspect the diff and acceptance criteria.
7. Fix material review findings.
8. Write `docs/roadmap/phase-N-report.md`.
9. Create a git commit:

```bash
git status --short
git add <phase files>
git commit -m "phase N: <short description>"
```

10. Report the commit hash and known limitations.

Do not begin the next phase until the current phase has a commit.

## Development constraints

- Preserve existing CLI behavior unless explicitly changed and documented.
- Keep heavyweight ML dependencies optional.
- Provide mock/no-model paths for UI and tests.
- Surface capability failures clearly in both UI and CLI.
- Do not silently export raster-only output without diagnostics explaining why object/vector tracks failed.
- Favor local-first operation. No required cloud service.
- Avoid storing sensitive paths/tokens in committed files.

## First action

Start with Phase 0. Spawn:

- `repo_archaeologist` to map current code, CLI commands, dependencies, tests, and extraction flow.
- `product_strategist` to validate user-facing goals against the roadmap.
- `qa_benchmark_engineer` to identify existing tests and minimal smoke fixtures.
- `reviewer` to list phase risks before implementation.

Then implement Phase 0 and commit it.
