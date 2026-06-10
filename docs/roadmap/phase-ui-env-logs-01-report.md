---
historical: true
default_context: false
---

# Phase UI-ENV-LOGS-01 Report

## Summary

Improved the Local UI run/setup visibility for long model jobs and added
environment-aware model guidance. The capability report now classifies the host
runtime, accelerator, and recommended provider path, so CUDA environments are
guided toward SAM3 Scene Sweep, Apple MPS environments toward SAM2 HF fallback,
and CPU-only environments toward CPU-safe workflows.

Run logs and setup logs now render a process overview, severity styling,
progress chips, progress bars, suggested recovery actions, and expandable debug
metadata. Model setup now shows a step-by-step playbook for environment
detection, runtime install, access check, model cache, server-side model path
recording, and setup verification.

The model cache flow now records a successful resolved model directory in
provider settings for runtime use, while browser/setup-job responses only expose
redacted path state. Setup job result storage and public setup-job helpers scrub
local paths before returning or persisting public job results.

## Changed Files

- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/backend/provider_setup_jobs.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_local_ui_api.py`
- `tests/test_provider_settings.py`
- `docs/local_ui.md`
- `docs/design/screenshots/ui-env-logs-01-before/`
- `docs/design/screenshots/ui-env-logs-01/`

## Browser Evidence

Baseline screenshots were captured under
`docs/design/screenshots/ui-env-logs-01-before/`. The first baseline layout run
captured 59 files across the core workflow states, then became stuck in the
cleanup path. A temporary detached worktree at the pre-change commit was used to
fill the missing 1920x1080 baseline matrix, adding 60 desktop-1920 screenshots.

After screenshots were captured under `docs/design/screenshots/ui-env-logs-01/`
with all required viewports: 390x844, 768x1024, 1024x768, 1366x768, 1440x900,
and 1920x1080. The after run captured 396 files and reported `status: ok`.
Both the after run and the detached-worktree 1920 baseline emitted a Python
`resource_tracker` semaphore cleanup warning after the layout script had already
reported success; no layout failures were reported.

Representative evidence inspected:

- `docs/design/screenshots/ui-env-logs-01/mobile-390-workflow-run-logs-open.png`
- `docs/design/screenshots/ui-env-logs-01/tablet-768-workflow-run-logs-open.png`
- `docs/design/screenshots/ui-env-logs-01/desktop-1440-workflow-run-logs-open.png`
- `docs/design/screenshots/ui-env-logs-01/desktop-1440-workflow-provider.png`
- `docs/design/screenshots/ui-env-logs-01/mobile-390-model-setup-cache-success-full.png`

## Tests Run

- `npm test`
- `npm run build`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-env-logs-01`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-env-logs-01-before --viewport desktop-1920` from a detached pre-change worktree reported `status: ok`; the wrapper exited 1 afterward because it used zsh's readonly `status` variable name
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_local_ui_api.py`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `git diff --check`

## Review

Used one read-only `diff-review-scout`. Findings were addressed before commit:

- Added phase report and completed missing 1920 baseline evidence.
- Added defense-in-depth local path redaction for public provider setup jobs and
  stored setup-job public results.
- Added CPU and Apple MPS recommendation coverage.

## Known Limitations

- GPU recommendation is based on local PyTorch/CUDA/MPS diagnostics. It does not
  perform a hosted call or a real model download unless the user explicitly runs
  setup actions.
- Model cache path recording is tested with mocked Hugging Face download and a
  local from-pretrained directory. A full real `facebook/sam3` download remains
  intentionally opt-in because it requires network, disk, and possible gated
  access.
- The sticky workflow footer can overlap the lower edge of long log panels at
  the bottom of narrow screenshots, but the layout checks pass and the log panel
  remains scrollable.

## Follow-Up Tasks

- Add a lightweight screenshot freshness helper that reports missing before or
  after viewport coverage before a phase reaches review.
- Consider a dedicated setup-job storage test for relative local model paths if
  relative path entry becomes a supported normal UI path.
- Add live CUDA/SAM3 smoke guidance documentation for Colab users once the SAM3
  runtime install path stabilizes.
