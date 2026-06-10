# Current Codex Task

## Active Task

`DOC-HARNESS-00`: reduce Codex documentation context.

## Goal

Reorganize repository documentation so default Codex context is small, explicit, current, validated, and committed.

Separate:

- current Codex operating context;
- stable safety invariants;
- current architecture truth;
- task-specific reference docs;
- human-facing docs;
- release docs;
- archived historical material.

## Must Read

- `docs/codex/START_HERE.md`
- `docs/codex/CURRENT_TASK.md`
- `docs/codex/SAFETY_INVARIANTS.md`
- `docs/codex/CURRENT_ARCHITECTURE.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`

## Must Not Read By Default

- `docs/archive/`
- `docs/roadmap/phase-*-report.md`
- old root docs
- old future plans
- old Codex planning packets
- completed roadmap reports
- old design/card-shell docs
- ignored local `codex_prompt_pack/` copies

Read those only when the user asks for historical analysis or a manifest route explicitly requires an archive index.

## Likely Files Touched

- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `codex_tasks.yaml`
- `docs/codex/*.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`
- `docs/archive/**`
- `docs/product/ui_redesign_brief.md`
- `docs/index.md`
- `README.md`
- `CONTRIBUTING.md`
- `scripts/check_codex_context_budget.py`
- `docs/roadmap/phase-doc-harness-00-report.md`

## Validation Commands

```bash
python3 scripts/check_codex_context_budget.py
python3 -m pytest -q tests/test_docs_links.py
git diff --check
```

Also run lightweight docs asset/link checks when available and relevant.

## Completion Checklist

- Root Codex entrypoints are compact shims.
- Default Codex read set is exactly the five required docs.
- Safety invariants are separated from UI-shape guidance.
- Current architecture is path-based and source-oriented.
- Task routing exists in `CONTEXT_MANIFEST.yaml`.
- Historical docs are archived or clearly marked non-default.
- Card/right-rail/stepper assumptions are not active redesign constraints.
- Context budget script exists and passes.
- Docs link test passes.
- Phase report exists.
- Diff is reviewed.
- Commit is created.

## Future Update Pattern

Future Codex tasks should update this file or replace it with a successor current-task file. Do not expand `AGENTS.md` or `CODEX_MASTER_PROMPT.md` with new long prompt bodies.
