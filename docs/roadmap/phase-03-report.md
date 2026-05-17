# Phase 03 Report: Screenshots, GIFs, and Demo Generation

Date: 2026-05-16

## Summary

Phase 03 added a repeatable README asset capture path. The new
`scripts/capture_docs_assets.py` command generates real local UI screenshots in
mock/no-model mode, runs the deterministic threshold red-ball extraction, and
creates a preview PNG plus a small GIF from generated frames and masks.

The public README now embeds the generated screenshots and demo assets instead
of deferring visual proof to placeholders. The asset inventory documents how to
regenerate the files and keeps the no-fake-screenshots policy explicit.

## Changed Files

- `README.md`
  - Embeds the local UI first-run screenshot, project setup, extraction wizard,
    provider diagnostics, job review, red-ball preview, and red-ball GIF.
  - Documents `scripts/capture_docs_assets.py --check` and full capture.
  - Updates Codespaces copy to reflect the Phase 02 devcontainer.
- `docs/assets/README_ASSETS.md`
  - Marks generated assets as real and documents regeneration commands.
  - Documents the browser-free red-ball-only path.
- `docs/assets/local-ui-first-run.png`
- `docs/assets/local-ui-new-project.png`
- `docs/assets/local-ui-extraction-wizard.png`
- `docs/assets/local-ui-provider-diagnostics.png`
- `docs/assets/local-ui-job-review.png`
- `docs/assets/canvas-preview-red-ball.png`
- `docs/assets/red-ball-demo.gif`
- `docs/repo_status.md`
  - Updates screenshot/demo and free-instance status.
- `scripts/capture_docs_assets.py`
  - Adds deterministic red-ball asset generation.
  - Starts the local UI in `--mock` mode with temporary backend storage.
  - Seeds a project, video, and mock extraction job through the real local API.
  - Captures UI screenshots with headless Chrome/Chromium when available.
  - Provides `--check` and `--skip-browser` smoke paths.
- `src/motionjson/ui/static/app.js`
  - Adds a query-parameter capture mode used only by documentation screenshots,
    including focused layouts for project setup, provider diagnostics, and job
    review.
- `tests/test_docs_assets.py`
  - Adds CI-safe checks for the capture script and generated README assets,
    including a guard against duplicate UI screenshots.

## Tests Run

- `python3 scripts/capture_docs_assets.py --check`
- `python3 scripts/capture_docs_assets.py`
- `python3 scripts/capture_docs_assets.py --skip-browser`
- `python3 -m py_compile scripts/capture_docs_assets.py`
- `node --check src/motionjson/ui/static/app.js`
- `python3 -m pytest -q tests/test_docs_assets.py`
- `python3 -m pytest -q tests/test_docs_assets.py tests/test_cli_ui.py tests/test_phase9_ui_job_review_smoke.py tests/test_ga_launch_docs.py`
  - Result: 14 passed.
- `python3 -m pytest -q`
  - Result: 232 passed.
- `npm run build`
- `npm test`
  - Result: 19 passed.
- `npm run lint`
- `git diff --check`

## Screenshots And Demos Produced

- `docs/assets/local-ui-first-run.png`
  - 1440x1000 local mock UI first-run state.
- `docs/assets/local-ui-new-project.png`
  - 1440x1000 seeded project/video state.
- `docs/assets/local-ui-extraction-wizard.png`
  - 1440x1000 goal-first extraction wizard state.
- `docs/assets/local-ui-provider-diagnostics.png`
  - 1440x1000 capability diagnostics showing no-model-ready providers.
- `docs/assets/local-ui-job-review.png`
  - 1440x1000 seeded mock job review state.
- `docs/assets/canvas-preview-red-ball.png`
  - 640x360 generated red-ball preview with real threshold mask overlay.
- `docs/assets/red-ball-demo.gif`
  - 320x180 generated red-ball mask-overlay animation.

## Known Limitations

- Full UI screenshot refresh requires Chrome or Chromium. The script exits
  cleanly with `--check` when no browser is available, and `--skip-browser`
  still refreshes the red-ball preview and GIF.
- The UI screenshots are static documentation captures. They do not exercise
  browser video playback because the smoke path intentionally stays no-model and
  deterministic.
- The screenshot capture mode is intentionally gated by `?capture=...`; normal
  local UI behavior is unchanged.
- The GIF is committed because it is small and provides immediate README visual
  proof. A future MP4/WebM can replace it if size or playback support becomes a
  problem.

## Follow-Up Tasks

- Phase 04 should link the asset regeneration instructions from the reorganized
  docs homepage.
- Future UI workflow changes should rerun `python3 scripts/capture_docs_assets.py`
  before updating README screenshots.
- Phase 09 should decide the broader generated-output policy for `out/` while
  keeping committed README assets intentional.
