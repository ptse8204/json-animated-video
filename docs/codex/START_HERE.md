# Codex Start Here

MotionJSON is a local-first video object tracing tool with a Python CLI/backend, static Local UI, and JS runtime/SDK.

Read only this default set first:

1. `docs/codex/START_HERE.md`
2. `docs/codex/CURRENT_TASK.md`
3. `docs/codex/SAFETY_INVARIANTS.md`
4. `docs/codex/CURRENT_ARCHITECTURE.md`
5. `docs/codex/CONTEXT_MANIFEST.yaml`

After the task subsystem is clear, use `CONTEXT_MANIFEST.yaml` for the smallest extra route.

Do not read archive, phase reports, old plans, old design docs, or bulky user docs unless the task route or user explicitly requires them.

Source and tests beat docs.

Obey `SAFETY_INVARIANTS.md`; it is UI-shape-free.

Scouts get only current task, invariants, relevant route, diff/tests/output, and snippets. They stay read-only unless explicitly authorized.

Run after docs changes:

```bash
python3 scripts/check_codex_context_budget.py
```
