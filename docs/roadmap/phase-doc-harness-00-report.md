# Phase DOC-HARNESS-00 Report

## Summary

Reorganized Codex documentation so the default read set is small, current, and route-based. Root Codex entrypoints now point to the harness instead of duplicating long prompt bodies. Safety invariants, current architecture truth, current task state, scout protocol, archive indexes, and UI redesign product guidance are separated.

## Files Changed Or Moved

- Added compact Codex harness docs:
  - `docs/codex/START_HERE.md`
  - `docs/codex/CURRENT_TASK.md`
  - `docs/codex/SAFETY_INVARIANTS.md`
  - `docs/codex/CURRENT_ARCHITECTURE.md`
  - `docs/codex/CONTEXT_MANIFEST.yaml`
  - `docs/codex/SCOUT_PROTOCOL.md`
- Shrunk root shims:
  - `AGENTS.md`
  - `CODEX_MASTER_PROMPT.md`
  - `codex_tasks.yaml`
- Added archive and product routing docs:
  - `docs/archive/README.md`
  - `docs/archive/phase_reports/README.md`
  - `docs/archive/codex_tasks_history.yaml`
  - `docs/product/ui_redesign_brief.md`
- Archived obsolete tracked prompt/root docs under:
  - `docs/archive/root_docs/`
  - `docs/archive/codex_prompts/`
- Marked completed roadmap reports with historical/non-default frontmatter while keeping them in `docs/roadmap/` for link stability.
- Marked path-stable legacy reference docs as historical/reference-only.
- Updated public/contributor navigation in `README.md`, `CONTRIBUTING.md`, `docs/index.md`, `docs/repo_status.md`, `docs/local_ui.md`, and design docs.
- Added `scripts/check_codex_context_budget.py`.
- Added docs-link tests for the harness in `tests/test_docs_links.py`.

## Default Codex Context

The default Codex read set is now exactly:

1. `docs/codex/START_HERE.md`
2. `docs/codex/CURRENT_TASK.md`
3. `docs/codex/SAFETY_INVARIANTS.md`
4. `docs/codex/CURRENT_ARCHITECTURE.md`
5. `docs/codex/CONTEXT_MANIFEST.yaml`

The budget check reports 5 files, 510 lines, 1,988 words, and 19,264 characters.

## Historical Material

- Old root docs moved to `docs/archive/root_docs/`.
- Old Codex prompt packets moved to `docs/archive/codex_prompts/`.
- Previous active `codex_tasks.yaml` content preserved at `docs/archive/codex_tasks_history.yaml`.
- Completed phase reports remain in `docs/roadmap/` but are marked historical and non-default.
- Old future plans and architecture/spec docs that remain path-stable for public docs/tests are marked historical or reference-only.
- Old card/right-rail/stepper guidance is no longer active redesign guidance; `docs/product/ui_redesign_brief.md` is form-agnostic.

## Validation

- `python3 scripts/check_codex_context_budget.py` - passed.
- `python3 -m pytest -q tests/test_docs_links.py` - passed, 10 tests.
- `python3 -m pytest -q tests/test_docs_assets.py` - passed, 4 tests.
- `python3 -m pytest -q tests/test_phase10_release_hardening.py` - passed, 4 tests.
- `python3 -m pytest -q tests/test_phase14_release_candidate.py` - passed, 3 tests.
- `git diff --check` - passed.

## Known Limitations

- Completed phase reports were not physically moved because release reports, public docs, and tests depend on their current paths.
- Ignored local `codex_prompt_pack/` copies may still exist in developer worktrees, but they are not tracked and are excluded from default context.
- Some older reference docs remain in place for compatibility and are marked non-default rather than deleted.

## Follow-up Tasks

- Keep `docs/codex/CURRENT_TASK.md` current for future tasks instead of expanding root prompts.
- Keep new subsystem routes in `docs/codex/CONTEXT_MANIFEST.yaml` narrow when adding docs.
- If public links are later migrated, phase reports can be physically moved under `docs/archive/phase_reports/`.
