---
historical: true
default_context: false
---

# UI-MODEL-10 Phase Report

## Summary

UI-MODEL-10 hardens the repository for release-candidate use without
overclaiming hosted service, model, or redistribution capabilities. The phase
adds public issue templates, expands the release checklist for the guided Local
UI/model connector work, documents license and repository-security boundaries,
and updates release/status docs so they match implemented features only.

## Changed Files

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/provider_setup_failure.yml`
- `.github/ISSUE_TEMPLATE/docs_report.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/ISSUE_TEMPLATE/config.yml`
- `README.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `docs/release_checklist.md`
- `docs/release_notes.md`
- `docs/repo_status.md`
- `docs/security_checklist.md`
- `tests/test_phase10_release_hardening.py`
- `docs/roadmap/phase-ui-model-10-report.md`

## Validation

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm --workspace @motionjson/runtime run test`
- `npm --workspace @motionjson/sdk run test`
- `npm pack --dry-run --workspace @motionjson/runtime`
- `npm pack --dry-run --workspace @motionjson/sdk`
- `python3 -m build --sdist --wheel`
- `python3 scripts/capture_docs_assets.py --check`
- `npm run ui:layout -- --screenshot-dir .motionjson/tmp/ui-model-10-layout-check`
- `docker build -t motionjson-ga .`
- `docker run --rm motionjson-ga python -m motionjson.cli backend diagnostics --json`
- `docker compose config`
- `git diff --check`

The full Python run passed with 415 tests and 1 skipped test. The transient
layout matrix generated 188 real browser screenshots under
`.motionjson/tmp/ui-model-10-layout-check`; those screenshots are validation
evidence only and are not committed because this phase did not change UI
layout. After the diff-review scout fixes, the focused release/docs guard
passed again with:

- `python3 -m pytest -q tests/test_phase10_release_hardening.py tests/test_docs_links.py tests/test_phase09_release_readiness.py tests/test_phase14_release_candidate.py`
- `git diff --check`

## Review Notes

- Read-only diff-review scout found three release-facing issues before commit:
  release notes omitted the no-license boundary, README still pointed Codex
  contributors at the historical roadmap, and the issue-template contact link
  implied private vulnerability reporting was already enabled. The phase now
  adds the release-note license boundary, updates README to point at the active
  UI/model roadmap, softens the security contact to `SECURITY.md`, and adds
  focused tests for those invariants.

## Known Limitations

- No `LICENSE` file is added in this phase. The repository continues to state
  that reuse, redistribution, and commercial rights are not granted until a
  maintainer chooses and adds an explicit license.
- Dependabot, secret scanning, branch protection, private vulnerability
  reporting, and signed/protected tags are documented repository-setting
  recommendations. This phase does not mutate GitHub repository settings.
- The issue templates are public-triage aids and do not replace private
  vulnerability reporting for sensitive security issues.

## Follow-Up Tasks

- Choose and add a license before publishing reusable packages or advertising
  redistribution/commercial rights.
- Configure GitHub repository settings for private vulnerability reporting,
  secret scanning, push protection, Dependabot alerts/updates, protected
  branches, required CI checks, and protected or signed release tags.
- Refresh README screenshots with `python3 scripts/capture_docs_assets.py` if a
  later UI phase changes documented UI surfaces.
