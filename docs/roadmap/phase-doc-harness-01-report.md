# Phase DOC-HARNESS-01 Report

## Summary

Contracted the active documentation corpus after `b47c4ec2`. Deleted stale prompt/spec/future-plan docs, old archive copies, old UI-shape docs, and completed phase reports from the working tree. Kept compact current Codex docs, user docs, final release summaries, and source/test routing.

## Metrics

| Metric | Before | After |
| --- | ---: | ---: |
| Tracked Markdown files | 284 | 79 |
| Tracked Markdown lines | 34,902 | 9,440 |
| Tracked Markdown chars | 1,527,479 | 400,615 |
| Default Codex lines | 510 | 239 |
| Default Codex chars | 19,264 | 9,279 |
| UI redesign routed docs | 5 docs / 1,228 lines / 61,241 chars | 3 docs / 85 lines / 4,936 chars |

## Deleted

- Old archived prompt/root copies under `docs/archive/codex_prompts/` and `docs/archive/root_docs/`.
- `docs/codex_future_plan.md` and `docs/codex_motionjson_*.md`.
- Old UI-shape docs `docs/design/local-ui-audit.md` and `docs/design/design-system.md`.
- Historical roadmap prompt `docs/roadmap/ui_model_connector_plan.md`.
- Completed phase reports under `docs/roadmap/`, except `phase-doc-harness-00-report.md`.

## Condensed

- `docs/codex/START_HERE.md`, `CURRENT_TASK.md`, `CURRENT_ARCHITECTURE.md`, `SAFETY_INVARIANTS.md`, and `CONTEXT_MANIFEST.yaml`.
- `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, and `codex_tasks.yaml`.
- `docs/local_ui.md`, `docs/product/ui_redesign_brief.md`, archive indexes, and final release/audit summaries.

## Kept

- User-facing setup/provider/runtime/security docs because they are linked from `docs/index.md` and contain current user guidance.
- `docs/roadmap/final-audit.md` and `docs/roadmap/final-qa-release-report.md` as compact release summaries.
- `docs/roadmap/phase-doc-harness-00-report.md` as the immediate prior phase summary.

## Validation

- `python3 scripts/check_codex_context_budget.py` - passed.
- `python3 -m pytest -q tests/test_docs_links.py` - passed.
- `python3 -m pytest -q tests/test_docs_assets.py` - passed.
- `python3 -m pytest -q tests/test_phase10_release_hardening.py tests/test_phase14_release_candidate.py tests/test_phase10_free_hosted_demos.py` - passed.
- `git diff --check` - passed.

## Known Limitations

- Remaining largest docs are user-facing references such as README, developer API, discovery providers, SAM docs, and troubleshooting.
- Full historical phase reports now require git history lookup.

## Follow-up

- Keep future current-task updates in `docs/codex/CURRENT_TASK.md`.
- Do not add full historical docs to `docs/archive/`; summarize and rely on git history.
