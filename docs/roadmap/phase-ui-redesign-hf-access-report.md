---
historical: true
default_context: false
---

# Phase Report: UI Redesign and Hugging Face Access Setup

## Summary

This phase repairs two first-run gaps in the main Local UI:

- The normal app shell now follows the storyboard structure more closely: persistent project rail on desktop, compact top stepper, single main task area, Advanced diagnostics rail only when opened, and a bottom workflow CTA instead of the old large wizard card.
- SAM3 Scene Sweep setup now asks for Hugging Face access in the main Model setup flow. The UI can save a Hugging Face token as a redacted local secret, then use server-owned setup jobs to check access and cache `facebook/sam3`.

The SAM3 backend setup path no longer depends on users pre-setting `HF_TOKEN` before launching the UI. Environment variables remain available for headless/advanced use.

## Changed Files

- `src/motionjson/provider_settings.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `tests/test_provider_settings.py`
- `tests/test_ui_first_run_simplicity.py`
- `docs/local_ui.md`
- `docs/sam3_local.md`
- `docs/design/screenshots/ui-redesign-hf-before/`
- `docs/design/screenshots/ui-redesign-hf-after/`

## Backend Notes

- Added optional `hf_token` credential metadata for `sam3-local`.
- `provider_runtime_settings()` now exposes raw credential values only to backend callers and includes `hf_token` for setup jobs.
- `check_access` and `cache_model` setup jobs save settings first when provided, read the saved Hugging Face token, and pass it to Hugging Face Hub calls.
- Browser-visible setup job payloads and results continue to use redaction; raw tokens and absolute local cache paths are not returned.

## UI Notes

- The Model setup status now reflects the setup state machine rather than only runtime diagnostics, so SAM3 can show `Needs Hugging Face access` even when local imports are otherwise ready.
- SAM3 Scene Sweep shows a normal-path Hugging Face token card before Advanced controls.
- `Change model` remains secondary, and raw paths, commands, logs, diagnostics, custom endpoints, and environment variables remain behind Advanced.
- The Start cards and Model setup panel were adjusted against the storyboard screenshots while preserving existing workflow/test contracts.

## Screenshots

Before and after matrices were captured in mock/no-model mode across:

- `390x844`
- `768x1024`
- `1024x768`
- `1366x768`
- `1440x900`
- `1920x1080`

Captured states:

- `workflow-goal`
- `workflow-video`
- `workflow-provider`
- `model-setup-sam3-local`
- `prepare-sam3-trace-all`
- `workflow-run`
- `workflow-review-failure`

Artifacts:

- Before: `docs/design/screenshots/ui-redesign-hf-before/`
- After: `docs/design/screenshots/ui-redesign-hf-after/`

## Validation

- `python3 -m pytest` - `490 passed, 1 skipped`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `npm test` - `21` Node tests passed
- `npm run lint`
- `npm run build`
- `node --check src/motionjson/ui/static/app.js`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-redesign-hf-after --state workflow-goal,workflow-video,workflow-provider,model-setup-sam3-local,prepare-sam3-trace-all,workflow-run,workflow-review-failure --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`

The layout command completed with `status: ok`. Python emitted the known shutdown `resource_tracker` semaphore warning after successful layout runs.

## Known Limitations

- The storyboard alignment is now materially closer, but it is still implemented as CSS/flow repair inside the existing shell rather than a full component-system rewrite.
- The Hugging Face token is stored in the existing local provider settings store. It is redacted in browser responses, but this local store is not a managed secrets vault.
- SAM3 access still depends on the user having accepted Meta/Hugging Face access terms for `facebook/sam3`.

## Follow-Up Tasks

- Continue tightening the visual match for the video import and review/export panels.
- Add an explicit token-delete action in the normal SAM3 access card.
- Consider replacing the CSS override layer with first-class shell component styles once the first-run flow stabilizes.
