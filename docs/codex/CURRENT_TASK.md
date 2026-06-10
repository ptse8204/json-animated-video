# Current Task

ID: `DOC-HARNESS-01`

Goal: contract the active documentation corpus after `b47c4ec2` so Codex context is smaller, old prompt/spec/design docs are gone, and future bloat is blocked by checks.

Likely files:

- `docs/codex/*.md`
- `docs/codex/CONTEXT_MANIFEST.yaml`
- `docs/product/ui_redesign_brief.md`
- `docs/local_ui.md`
- `docs/index.md`, `README.md`, `CONTRIBUTING.md`
- `docs/archive/README.md`, `docs/archive/phase_reports/README.md`
- `scripts/check_codex_context_budget.py`
- `tests/test_docs_links.py`
- `docs/roadmap/phase-doc-harness-01-report.md`

Validation:

```bash
python3 scripts/check_codex_context_budget.py
python3 -m pytest -q tests/test_docs_links.py
python3 -m pytest -q tests/test_docs_assets.py
git diff --check
```

Done when:

- default read set is <= 350 lines and <= 25,000 chars;
- `ui_redesign` route has <= 3 compact docs and no old UI/design/roadmap/archive docs;
- tracked Markdown lines decrease from the before metric;
- stale archived prompt/spec copies and old phase reports are removed or summarized;
- phase report records before/after metrics;
- commit message is `phase doc-harness-01: contract active documentation corpus`.

Future tasks should replace this file, not expand root prompts.
