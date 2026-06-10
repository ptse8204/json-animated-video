---
historical: true
default_context: false
---

# Phase UI-MODEL-01 Report

## Summary

Added a nontechnical first-run workflow to the local UI. The workspace now leads
with plain-language goal cards, a keyboard-accessible browser preview action, a
readable run-plan summary, and raw `ExtractionRunConfig` JSON behind an
Advanced disclosure. Backend local path registration remains available under
Advanced so CPU/mock workflows and CLI-compatible run configs are preserved.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_phase03a_local_ui_layout.py`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-model-01-before/`
- `docs/design/screenshots/ui-model-01/`
- `docs/roadmap/phase-ui-model-01-report.md`

## Browser Evidence

Before screenshots:

- `docs/design/screenshots/ui-model-01-before/`

After screenshots:

- `docs/design/screenshots/ui-model-01/`

Representative after captures:

- `docs/design/screenshots/ui-model-01/mobile-390-first-run.png`
- `docs/design/screenshots/ui-model-01/tablet-1024-first-run.png`
- `docs/design/screenshots/ui-model-01/desktop-1440-first-run.png`
- `docs/design/screenshots/ui-model-01/mobile-390-advanced-config.png`
- `docs/design/screenshots/ui-model-01/mobile-390-advanced-config-full.png`
- `docs/design/screenshots/ui-model-01/desktop-1440-advanced-config.png`

The layout gate now includes an `advanced-config` state so the raw JSON
disclosure is validated separately from the fully expanded stress state. At
390px, that state also writes a full-page screenshot so the raw JSON disclosure
and backend local path disclosure are visible in the evidence set.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-01`
- `python3 -m pytest -q tests -k "ui"`
- `python3 -m motionjson.cli ui --help`
- `git diff --check`

The mock UI layout command still emits the known Python resource tracker leaked
semaphore warning during shutdown, but exits successfully.

## Known Limitations

- The browser preview action loads a local file for drawing only. Extraction
  jobs still require local path registration through the Advanced disclosure
  until a server-side upload/copy endpoint is intentionally added.
- The guided plan is deterministic UI logic, not model-assisted planning. Model
  connector contracts begin in UI-MODEL-02.
- Review cards and export handoff remain largely as they were after
  UI-LAYOUT-01; those are scheduled for UI-MODEL-07 and UI-MODEL-08.

## Follow-Up Tasks

- Add a server-side model connector contract in UI-MODEL-02 without exposing
  credentials to browser code.
- Revisit actual upload/copy semantics when the backend can safely store user
  selected browser files.
- Continue replacing default JSON-first surfaces with validated, reviewable
  plain-language plans while preserving CLI/debug access.
