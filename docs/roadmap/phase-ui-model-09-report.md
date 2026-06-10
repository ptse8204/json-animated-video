---
historical: true
default_context: false
---

# UI-MODEL-09 Phase Report

## Summary

UI-MODEL-09 adds Codex-ready operational prompt documentation for continuing
the active Local UI/model connector roadmap safely. The new prompt pack covers
master phase kickoff, UI layout review, browser screenshot review, model
connector review, release audit, and the approved read-only scout roles.

The repo-level Codex instructions now point future agents to this prompt pack
and explicitly guard against automation that can push commits, publish packages,
mutate provider settings, or call hosted providers without human review.

## Changed Files

- `docs/codex/ui_model_operational_prompts.md`
- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `docs/index.md`
- `docs/roadmap/phase-ui-model-09-report.md`

## Validation

- `python3 -m pytest -q tests/test_docs_links.py`
- `python3 -m pytest -q tests/test_phase09_release_readiness.py`
- `git diff --check`
- Manual review of `.github/workflows/ci.yml` confirmed this phase did not add
  new automation or push/publish behavior.
- Read-only diff-review scout found that several copy-ready scout prompts did
  not repeat the full safety restriction text. The prompt pack now repeats the
  no-edit, no-install, no-configuration-change, no-push, no-publish,
  no-hosted-call, and no-spawn-agent restrictions in every scout prompt.

## Known Limitations

- The prompt pack is documentation only. It does not add a GitHub Action or
  any automated Codex execution.
- The prompts rely on future Codex sessions following the repo instructions and
  active roadmap.

## Follow-Up Tasks

- UI-MODEL-10 should fold these prompts into the release checklist where useful
  and verify that release hardening docs still match implemented features only.
