# Phase DOC-HARNESS-00 Report

Commit: `b47c4ec2 phase doc-harness-00: reduce codex documentation context`

## Summary

Created the compact Codex harness:

- `docs/codex/START_HERE.md`
- `docs/codex/CURRENT_TASK.md`
- `docs/codex/SAFETY_INVARIANTS.md`
- `docs/codex/CURRENT_ARCHITECTURE.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`

It also introduced archive indexes, a UI redesign brief, and `scripts/check_codex_context_budget.py`.

## Superseded By

`DOC-HARNESS-01` contracted the corpus further by deleting duplicate old prompt/spec docs, old archive copies, and completed phase reports from the working tree.

## Validation Recorded

- `python3 scripts/check_codex_context_budget.py`
- `python3 -m pytest -q tests/test_docs_links.py`
- `python3 -m pytest -q tests/test_docs_assets.py`
- `git diff --check`
