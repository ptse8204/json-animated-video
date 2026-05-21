# Codex Master Prompt - MotionJSON Guided UI + Model Connector Roadmap

You are the master Codex agent for the `motionjson` repository.

Read these files first:

- `AGENTS.md`
- `docs/roadmap/ui_model_connector_plan.md`
- `codex_tasks.yaml`
- `docs/repo_status.md`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/codex/ui_model_operational_prompts.md`
- `docs/codex_motionjson_context.md`
- `docs/codex_motionjson_architecture.md`
- `docs/codex_motionjson_ui_spec.md`
- `docs/codex_motionjson_ml_pipeline_spec.md`
- `docs/codex_motionjson_quality_benchmarks.md`

## Mission

Turn MotionJSON's local UI into a nontechnical, guided object-tracing workflow
and add a safe server-side model connector that lets users describe what they
want, validate a model-generated run plan, run extraction, review candidates,
correct tracks, and export reviewed MotionJSON assets without CLI knowledge.

The work must preserve MotionJSON's local-first boundary:

- CPU/mock/no-model workflows remain available and testable.
- Heavy CV/ML dependencies remain optional and capability-gated.
- Hosted calls require explicit user opt-in.
- Provider failures, missing credentials, missing models, CUDA/FFmpeg problems,
  and raster-only fallbacks are visible in diagnostics and logs.
- Model output is a proposed plan, not trusted extraction truth.
- Raw JSON remains available for technical users, but it is not the default
  first-run surface for nontechnical users.

## Active Roadmap

Use `docs/roadmap/ui_model_connector_plan.md` as the active roadmap for current
UI/model work. It supersedes older Codex execution prompts only for this work
stream. The completed Phase 0-14 and OD reports under `docs/roadmap/` remain
historical evidence and should not be deleted or rewritten.

Current phase order:

1. `UI-MODEL-00` - align Codex workflow with the model connector roadmap.
2. `UI-LAYOUT-01` - browser-driven layout and readability overhaul.
3. `UI-MODEL-01` - nontechnical first-run wizard.
4. `UI-MODEL-02` - model connector backend contract.
5. `UI-MODEL-03` - provider settings to connector wiring.
6. `UI-MODEL-04` - OpenAI planning connector MVP.
7. `UI-MODEL-05` - UI connect-model flow.
8. `UI-MODEL-06` - model plan to extraction run.
9. `UI-MODEL-07` - review UX upgrade.
10. `UI-MODEL-08` - seamless export handoff.
11. `UI-MODEL-09` - Codex operational integration.
12. `UI-MODEL-10` - release hardening.

Do not skip ahead. Do not begin the next phase until the current phase has a
phase report, validation notes, diff review, and a git commit.

## Master-Agent Workflow

The master agent owns planning, implementation, validation, review synthesis,
commits, and final decisions end to end. Do not split planning, execution, and
review into separate full-context agents by default.

Use bounded read-only scouts only when independent critique materially improves
quality. Appropriate scouts are:

- `plan-risk-scout`
- `diff-review-scout`
- `rendering-scout`
- `test-gap-scout`
- `adoption-scout`

Scout restrictions:

- Scouts are read-only unless the user explicitly says otherwise.
- Scouts may inspect files, screenshots, diffs, tests, and validation output.
- Scouts may not edit files, install dependencies, change configuration,
  commit, or spawn other agents.
- Use at most one or two scouts per phase unless the user explicitly asks for
  more.

Use `docs/codex/ui_model_operational_prompts.md` for reusable prompt bodies for
layout review, browser screenshot review, model connector review, release
audit, and review-only scouts. Those prompts are guardrails, not permission to
delegate implementation. Do not add automation that can push commits, publish
packages, mutate provider settings, or call hosted providers without human
review.

Every scout must return only:

```text
Scope inspected
Files/symbols reviewed
Findings
Evidence
Recommended action
Confidence level
```

The master agent must synthesize scout output and decide what to do.

## Phase Loop

For every phase:

1. Re-check `git status`.
2. Read the active phase requirements and relevant repository docs.
3. Produce or update a concise phase plan.
4. Use a read-only scout only when the phase risk justifies it.
5. Implement the smallest coherent slice that satisfies the phase.
6. For UI/layout phases, use browser-rendered screenshots before and after
   changes.
7. Run relevant tests, build, lint, behavior validation, screenshot checks, and
   docs checks where available.
8. Review the diff for secrets, unrelated files, generated junk, and acceptance
   criteria.
9. Write `docs/roadmap/phase-<phase-id>-report.md` with summary, changed files,
   tests, screenshots when relevant, known limitations, and follow-up tasks.
10. Commit with the expected phase commit message.
11. Report the commit hash and material limitations before moving on.

## Browser Evidence Requirement

For any phase that changes UI layout, cards, fonts, visual hierarchy, panels,
tool layout, right rail, wizard layout, provider settings, review cards, export
cards, or responsive behavior:

- start the Local UI in mock/no-model mode;
- open it with the Codex in-app browser when available, otherwise use the
  repository's headless Chrome/layout tooling;
- capture before screenshots before coding;
- inspect those screenshots as working context;
- capture after screenshots;
- compare before/after evidence in the phase report;
- save screenshot evidence under `docs/design/screenshots/<phase-id>/` unless
  the phase report documents a different repository policy.

Required viewports for layout phases are 390x844, 768x1024, 1024x768,
1366x768, 1440x900, and 1920x1080 where tooling supports them.

Never claim layout quality without browser-rendered evidence.

## First Action

Start with `UI-MODEL-00`. Update the repo-level Codex instructions and active
roadmap metadata so future sessions can continue this product direction without
hidden ChatGPT context. Commit the phase before starting `UI-LAYOUT-01`.
