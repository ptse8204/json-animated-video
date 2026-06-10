---
historical: true
default_context: false
---

# Phase Report: Colab Setup Token Confirmation

## Summary

Live Chrome QA against the Colab Local UI reproduced the setup-flow blocker:
after a Hugging Face token was entered, clicking `Check Hugging Face access`
rendered the in-app confirmation and cleared the password field before the
confirmed setup action read it. The resulting server job ran without the token
and returned the normal missing-token guidance. A blocked access job then made
the guided primary CTA regress to `Retry setup`, routing users toward install
recovery instead of keeping them on the access step.

The UI now keeps the current setup form DOM until the confirmed action has read
password fields, and terminal `check_access`/access-related `cache_model`
failures keep the model setup state on the access CTA instead of switching to
unrelated install recovery.

In the current deployed Colab session, saving the token first from Advanced was
a workable manual bypass: the Hugging Face access check completed with the
saved redacted credential and the flow advanced to `Cache model`. The
subsequent `facebook/sam3` cache job was started and remained in `Caching
model` / `Setup running` during this validation window.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_config_builder.mjs`
- `docs/design/screenshots/phase-colab-setup-token-confirmation/`
- `docs/roadmap/phase-colab-setup-token-confirmation-report.md`

## Browser Evidence

- Live Chrome tab:
  `https://8766-gpu-g4-s-kkb-euw4a2-ufumxgd7l64s-a.europe-west4-2.prod.colab.dev/ui/`
- Reproduced normal flow: Start -> Find everything in scene -> Video ->
  Model setup.
- Observed pre-fix live behavior:
  - SAM3 selected while the guided primary CTA showed `Retry setup`;
  - entering the Hugging Face token did not change the primary CTA;
  - clicking `Check Hugging Face access` rendered confirmation, then the
    confirmed job reported missing token because the password input had been
    cleared by the confirmation render;
  - saving the token first from Advanced allowed the access check to pass.
- After local patch, layout screenshots were captured for
  `model-setup-sam3-local` and `model-setup-confirm-cache` at:
  `390x844`, `768x1024`, `1024x768`, `1366x768`, `1440x900`, and
  `1920x1080`.

## Tests Run

- `node --check src/motionjson/ui/static/app.js` - passed.
- `npm test` - passed, 21 tests.
- `python3 -m pytest -q tests/test_provider_settings.py::test_sam_setup_jobs_cache_models_with_confirmation_and_redaction` - passed.
- `npm run build` - passed.
- `npm run ui:layout -- --state model-setup-sam3-local,model-setup-confirm-cache --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-colab-setup-token-confirmation` - passed with the existing Python `resource_tracker` semaphore warning at shutdown.
- `git diff --check` - passed.

## Known Limitations

- The live Colab deployment used for QA was not patched in-place, so it still
  needs a restart/redeploy from this commit to get the confirmation fix.
- The live `facebook/sam3` cache job exposes only coarse `Setup running`
  feedback; no byte-level progress, rate, or ETA is available in the UI.
- No real extraction run was completed after caching because the live cache job
  was still running during the validation window.
- Full `python3 -m pytest` was not rerun for this narrow UI-flow fix.

## Follow-Up Tasks

- Restart or redeploy the Colab UI from this commit and rerun the normal
  token -> access check -> cache model flow without the Advanced save
  workaround.
- Add browser-level non-mock coverage for confirmed setup actions with password
  fields.
- Add setup-job progress details for Hugging Face downloads when the underlying
  dependency exposes stable progress callbacks.
