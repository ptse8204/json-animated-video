# Phase 9 Report

## Summary

Phase 9 adds local UI job execution and result review. The UI can now start
extract jobs from the selected project/video and generated run config, poll job
progress, display job events/logs, browse generated artifacts, show fallback
diagnostics, and render reviewed object tracks over the video viewer.

The backend local UI API now accepts full `runConfig` payloads that reference
registered assets, starts the local worker on demand, exposes progress snapshots,
serves safe visual artifact content, and returns sanitized artifact review
metadata for tracks, scene objects, provider diagnostics, failures, and raster
fallbacks. Provider execution remains gated to deterministic local providers
for the UI worker: `mock`, `threshold`, and `external`.

Subagents used: backend/API worker, frontend UI worker, QA worker, and reviewer.
Reviewer findings were addressed by gating synthetic tracks away from terminal
fallback/failed jobs, redacting plain storage-key paths in review text, and
making the local worker wait briefly for just-queued work before exiting.

## Working Tree Baseline

Phase 9 did not start from a clean working tree. Pre-existing unrelated changes
were present in `README.md`, `out/demo/**`, `AGENTS_old.md`, `README_old.md`,
and generated preview/runtime files under `out/demo/preview/**`. They are not
part of Phase 9 and are intentionally excluded from the Phase 9 commit.

## Changed Files

- `docs/roadmap/phase-9-report.md`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_local_ui_api.py`
- `tests/test_phase9_ui_job_review_smoke.py`

## Tests Run

- `python -m pytest tests/test_phase9_ui_job_review_smoke.py -q` failed
  because `python` is not installed on PATH.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py tests/test_phase9_ui_job_review_smoke.py -q` passed: 14 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q` passed: 197 passed.
- `node --check src/motionjson/ui/static/app.js` passed.
- `node --check scripts/build_ui_shell.mjs` passed.
- `node scripts/test_ui_config_builder.mjs` passed.
- `npm run build` passed.
- `npm test` passed: 19 passed.
- `npm run lint` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help` passed.
- Browser smoke passed in mock mode at `http://127.0.0.1:8777/`: created a
  project, registered a temporary H.264 demo video, started a mock extraction
  from the UI, and verified `succeeded`, 122 events, 188 artifacts, one reviewed
  track, and `640x360 px` video metrics. Screenshot:
  `/tmp/phase9-ui-smoke-final.png`.
- `git diff --check` passed.

## Known Limitations

- The local UI worker is an in-process background thread for local runs. It is
  enough for mock/CPU smoke checks, but not a durable multi-process queue runner.
- Browser preview still depends on browser-decodable source video. The repository
  demo MP4 uses `mp4v`, so browser smoke used a temporary H.264 copy.
- Full manual correction/edit workflows remain later-phase work. Phase 9 reviews
  tracks and diagnostics but does not yet write correction edits from the UI.
- Heavy ML providers remain optional and capability-gated. The UI start path
  rejects SAM2 and detector-backed execution until a deterministic local worker
  adapter is explicitly added.

## Follow-Up Tasks

- Add UI controls for track include/exclude edits and persistence.
- Add a durable worker/process mode for long-running local jobs.
- Add explicit artifact open/download actions where safe for local-only content.
- Add correction authoring against reviewed tracks and masks in the next UI
  review/correction phase.
