---
historical: true
default_context: false
---

# Phase OD-14 Report - Documentation, Screenshots, Benchmarks, And Release Polish

## Summary

Phase OD-14 completes the documentation pass for the API-first object discovery
roadmap. The README, docs index, release notes, release checklist, repository
status, troubleshooting, benchmark, security, and migration docs now state the
default workflow clearly: Clean discovery first, API-returned candidate review,
selected-candidate tracking, and review-gated export of JSON-controlled motion
layers.

The docs also mark Maximum Recall as advanced, Trace Everything as
expert/experimental and review-required, SAM2 as the optional practical
lower-cost proposal path when configured, and SAM3 as optional for concept,
exemplar, and higher-recall discovery. Hosted provider docs continue to require
explicit network, hosted, and cost/privacy acknowledgement before any hosted
test or run sends frames.

## Changed Files

- `README.md`
- `docs/index.md`
- `docs/release_checklist.md`
- `docs/release_notes.md`
- `docs/repo_status.md`
- `docs/benchmark_fixtures.md`
- `docs/troubleshooting.md`
- `docs/security/api_keys.md`
- `docs/migration_and_known_limitations.md`
- `tests/test_docs_links.py`
- `docs/roadmap/phase-od-14-report.md`

## Tests Run

- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m motionjson.cli backend diagnostics --json`
- `git diff --check`

## Screenshots And Assets

- No screenshot assets were regenerated in this phase because the UI code and
  documented visual states did not change.
- `python3 scripts/capture_docs_assets.py --check` is part of final validation
  to confirm the screenshot tooling and asset directory remain healthy.

## Known Limitations

- Real SAM2 and SAM3 execution remains optional and environment-dependent.
  The docs intentionally do not claim those providers are bundled with the
  base install.
- Hosted SAM3 smoke tests and hosted discovery remain opt-in and require
  explicit cost/privacy acknowledgement. No docs or tests include real secrets.
- Browser screenshot refresh remains a local/docs maintenance step; OD-14 uses
  the existing committed assets and layout checks.
- Adoption scout was attempted before commit, but the Codex app returned
  `agent thread limit reached`. Direct docs review plus docs, layout, and
  release validation covered the changed surfaces instead.

## Follow-up Tasks

- Regenerate screenshots after any future visible Local UI changes.
- Add release-note examples for real SAM2/SAM3 environments once supported
  model setup is tested outside CI.
