---
historical: true
default_context: false
---

# Phase 03B Report - Provider Key And Model Selection Settings

## Summary

Phase 03B added a Local UI provider settings experience for bring-your-own-key
configuration, model selection, readiness checks, and cost/privacy disclosure.
The settings surface keeps mock/no-model paths as the safe default, separates
local and hosted providers, shows redacted credential state, and never returns
raw keys from public UI APIs.

Provider settings are stored locally in the existing SQLite backend and exposed
through redacted API responses. Environment variables still take precedence over
saved Local UI settings. Hosted settings saved through the UI are reported as
configuration-only until runtime routing explicitly consumes those stored keys;
this avoids claiming a hosted provider is runnable when the extraction runtime
cannot yet use that credential path.

## Changed Files

- `.env.example`
- `README.md`
- `docs/assets/README_ASSETS.md`
- `docs/assets/local-ui-*.png`
- `docs/design/screenshots/phase-03b/*`
- `docs/index.md`
- `docs/local_ui.md`
- `docs/privacy.md`
- `docs/provider_capabilities.md`
- `docs/security/api_keys.md`
- `scripts/check_local_ui_layout.mjs`
- `src/motionjson/backend/db.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/providers/openrouter.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_phase03b_provider_settings_ui.py`
- `tests/test_provider_settings.py`

## UI And Settings Improvements

- Added a right-rail Provider settings panel with provider rows, locality chips,
  readiness state, cost/privacy warnings, model selection, hosted opt-in,
  endpoint/base URL fields, and Save/Test/Reset actions.
- Added default safe mock/no-model settings and kept hosted network calls behind
  explicit opt-in.
- Added API-key entry fields that clear after save and only show redacted
  credential state after persistence.
- Added OpenRouter-style provider metadata with base URL and custom model
  support.
- Added provider capability diagnostics that distinguish runnable environment
  configuration from settings-only Local UI credentials.
- Added URL validation for hosted endpoint/base URL values.
- Added redaction for provider settings, diagnostics, errors, logs, exported
  settings, bearer tokens, query strings, and MotionJSON/OpenRouter-shaped keys.

## Screenshots And Demos

The full Phase 03B layout matrix was captured in:

- `docs/design/screenshots/phase-03b/`

The matrix contains 36 screenshots across 1366px, 1440px, 1920px, and 1024px
viewports for the real shell, seeded shell, expanded shell, docs capture states,
provider diagnostics, provider settings, and job review.

README screenshots were regenerated through the real local UI capture path:

- `docs/assets/local-ui-first-run.png`
- `docs/assets/local-ui-new-project.png`
- `docs/assets/local-ui-extraction-wizard.png`
- `docs/assets/local-ui-provider-diagnostics.png`
- `docs/assets/local-ui-job-review.png`

## Validation Run

- `python3 -m pytest -q` - passed, 302 tests.
- `npm run build && npm test && npm run lint` - passed, 19 Node tests plus lint.
- `npm run ui:layout` - passed across the full viewport/state matrix.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-03b` -
  passed and generated 36 screenshots.
- `npm run ui:layout -- --state provider-settings,real-empty-shell --viewport laptop-1366,tablet-1024` -
  passed.
- `python3 scripts/capture_docs_assets.py` - passed and regenerated README
  assets.
- `python3 scripts/capture_docs_assets.py --check` - passed with Chrome
  available.
- `python3 -m motionjson.cli backend diagnostics --json` - passed; follow-up
  scans found no raw OpenRouter, MotionJSON local, or bearer-token secrets in
  the JSON output.
- `python3 -m pytest tests/test_provider_settings.py tests/test_capabilities.py -q` -
  passed, 23 tests.
- `python3 -m pytest tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py::test_local_ui_run_config_validation_uses_existing_config_code_and_warns -q` -
  passed, 24 tests.
- `node --check src/motionjson/ui/static/app.js` - passed.
- `git diff --check` - passed.

The layout smoke command still emits a Python multiprocessing resource-tracker
semaphore warning while the mock worker shuts down in this environment. The
command exits successfully after the DOM overlap/overflow checks pass.

## Review Fixes

The read-only plan-risk scout flagged that diagnostics previously only reflected
environment configuration, that public redaction missed some API-key-shaped
strings, and that hosted provider failures could surface raw transport details.
The implementation added local settings storage, broader redaction, and
OpenRouter error redaction.

The read-only diff-review scout flagged that UI-saved hosted credentials were
initially reported as runnable even though runtime provider construction still
uses environment/constructor configuration. Capability diagnostics now mark
those saved credentials as `configured_settings_only` and `settingsOnly: true`.
The scout also flagged endpoint validation; hosted endpoints and OpenRouter base
URLs now require valid `http://` or `https://` URLs before save.

## Known Limitations

- Saved hosted provider credentials are settings and diagnostics data only until
  a later phase wires them into extraction job runtime construction.
- Provider secrets are stored in the local SQLite database. They are redacted
  from UI/API responses and logs, but the local database is not a managed secret
  vault.
- Provider connectivity tests are non-network readiness checks in this phase.
  They validate configuration shape and opt-in state without making hosted
  calls.
- The settings UI remains vanilla HTML/CSS/JavaScript with no frontend
  framework migration.

## Follow-Up Tasks

- Wire saved hosted provider settings into actual extraction runtime creation
  once job execution has an explicit settings resolution path.
- Add real provider connectivity checks behind an explicit network action.
- Add visual diff comparison if the project adopts a browser regression
  baseline tool.
