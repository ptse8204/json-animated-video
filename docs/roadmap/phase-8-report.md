---
historical: true
default_context: false
---

# Phase 8 Report

## Summary

Phase 8 adds the local UI video prompt workspace and goal-first extraction
wizard. The UI now exposes the required presets:

- Trace one object.
- Find objects from text.
- Propose all visible segments.
- Find moving objects.
- Import external masks.

The workspace includes a video viewer, point/box/brush/erase/label/keyframe
tools, native-video-pixel coordinate mapping, prompt summaries, advanced
threshold/FPS/device/model controls, config preview, config save/load, and
backend validation before run creation. Text prompts map to `text_detector`
discovery and never raw SAM2. Moving-object discovery uses the local `motion`
mask provider path. Unavailable providers are shown before validation or run
work, with mock/no-model alternatives still visible.

The local API now provides safe registered-video playback through
`/api/videos/{videoId}/content` with byte ranges and `HEAD`, plus
`POST /api/run-config/validate` backed by `ExtractionRunConfig` and provider
policy diagnostics. Public video/job/artifact payloads continue to scrub storage
keys and local file paths.

Subagents used: frontend UI worker, product strategy worker, backend/API
worker, QA worker.

## Working Tree Baseline

Phase 8 did not start from a clean working tree. Pre-existing unrelated changes
were present in `README.md`, `out/demo/**`, `AGENTS_old.md`, `README_old.md`,
and generated preview/runtime files under `out/demo/preview/**`. They are not
part of Phase 8 and are intentionally excluded from the Phase 8 commit.

## Changed Files

- `docs/developer_api.md`
- `docs/local_ui.md`
- `docs/run_config.md`
- `docs/roadmap/phase-8-report.md`
- `package.json`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_local_ui_api.py`
- `tests/test_phase8_ui_config_builder.py`

## Tests Run

- `python -m pytest tests/test_phase8_ui_config_builder.py -q` failed because
  `python` is not installed on PATH.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py tests/test_phase8_ui_config_builder.py -q` passed: 13 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q` passed: 192 passed.
- `node --check src/motionjson/ui/static/app.js` passed.
- `npm run build` passed.
- `node scripts/test_ui_config_builder.mjs` passed.
- `npm test` passed: 19 passed.
- `npm run lint` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` passed.
- Browser smoke passed in mock mode at `http://127.0.0.1:8767/`: created a
  project, registered a source video, selected the text-detector preset,
  validated the generated config with provider warnings, loaded a temporary
  H.264 preview video through `/api/videos/{id}/content`, and added a positive
  point that produced native coordinates in config.
- `git diff --check` passed.

## Known Limitations

- The Phase 8 UI validates and saves generated run configs, but `POST /api/jobs`
  still accepts the Phase 7 simple job payload. Full queued execution from the
  saved run config remains a follow-up.
- Browser preview depends on a browser-decodable video codec. The repository
  demo MP4 uses `mp4v`, so the browser smoke used a temporary H.264 copy for
  metadata/canvas verification.
- Heavy discovery/segmentation providers remain optional and capability-gated.
  Missing SAM2, detector packages, CUDA, model weights, and hosted settings are
  reported as warnings rather than hidden.

## Follow-Up Tasks

- Wire backend jobs to accept and persist the full validated run config.
- Add richer edit/delete controls for prompts and mask strokes.
- Add review/correction workflows for existing extraction results in the next
  UI phase.
