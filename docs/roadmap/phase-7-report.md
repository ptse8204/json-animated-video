# Phase 7 Report - Local API Server And UI Shell

## Summary

Phase 7 adds a local-first UI foundation that runs without GPU, model weights,
hosted services, or frontend runtime dependencies. The new `motionjson ui`
command serves a packaged static shell and a dependency-light stdlib HTTP API
over the existing SQLite backend and local filesystem storage.

The local API now exposes health, provider capabilities, run-config defaults,
export formats, projects, videos, jobs, progress, events, and artifacts. Public
asset/job/event payloads scrub internal storage keys and local `file://`
storage URIs. Mock/no-model mode is visible in health and run defaults, while
provider diagnostics still report missing CUDA, SAM2, detector, FFmpeg, or
optional dependency failures instead of hiding them.

The frontend shell shows local API health, mock/no-model status, provider
capability diagnostics, project creation/selection, local video registration,
video selection, job status/progress, and route visibility. Extraction wizard
controls remain for Phase 8.

The worktree was not clean at the start of this phase because unrelated
generated `out/demo/**` files and `README.md` edits were already present. Those
unrelated files were not modified for this phase and are not part of the phase
commit.

## Changed Files

- `src/motionjson/ui/__init__.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/cli.py`
- `scripts/build_ui_shell.mjs`
- `tests/test_local_ui_api.py`
- `tests/test_cli_ui.py`
- `docs/local_ui.md`
- `docs/index.md`
- `docs/developer_api.md`
- `docs/saas_backend.md`
- `docs/roadmap/phase-7-report.md`
- `package.json`
- `pyproject.toml`

## Subagents

- Backend/API worker: verified and extended the local UI API, response
  scrubbing, mock job queueing, progress/events/artifacts, and API tests.
- Frontend UI worker: verified the dependency-free shell, visible
  mock/no-model state, capability diagnostics, job progress UI, route checks,
  and frontend build smoke.
- Release packaging/docs worker: verified package data, launch command docs,
  local-first/no-secrets/no-model guidance, and documentation links.
- QA worker: independently ran the required `python` check, `python3` API
  slice, full Python and npm suites, and a local UI smoke.

## Tests And Checks Run

Required command, unavailable in this environment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python -m pytest tests -k api -q
# zsh:1: command not found: python
```

Equivalent API slice:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k api -q
# 16 passed, 170 deselected
```

Focused new tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py tests/test_cli_ui.py -q
# 9 passed
```

Frontend build smoke:

```bash
npm run build
# ok; checked index.html, app.css, app.js
```

CLI smoke:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help
# passed
```

Full-suite checks:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -q
# 186 passed
npm test
# 18 passed
npm run lint
# passed
git diff --check
# passed
```

## Local UI Smoke

QA started the local UI with a temporary database and storage root:

```bash
python3 -m motionjson.cli ui \
  --db /tmp/motionjson-phase7-smoke/backend.sqlite \
  --storage-root /tmp/motionjson-phase7-smoke/storage \
  --host 127.0.0.1 \
  --port 8765 \
  --no-open \
  --mock
```

The browser smoke verified that `http://127.0.0.1:8765/` displayed the
MotionJSON shell, tracing goals, local API status `ok`, mock mode `on`, and
capability summary. `/api/health` returned `localFirst: true` and
`mockMode: true`; `/api/capabilities` returned provider diagnostics with
missing optional provider reasons visible.

The main integration pass also started the Python UI server on
`http://127.0.0.1:8767/` with a temporary database/storage root. Browser
automation verified the MotionJSON shell, Local API panel, Capabilities panel,
Mock/no-model panel, Jobs panel, route list, project creation, and local video
registration/selection for `examples/demo_red_ball.mp4`. The smoke server was
stopped.

A follow-up browser resmoke after reviewer fixes started the Python UI server
on `http://127.0.0.1:8769/`, verified the video picker/list selection controls,
created a project, and confirmed the threaded local-user creation race no
longer produced a server error. The smoke server was stopped.

## Known Limitations

- The Phase 7 shell lists and enqueues local jobs, but the goal-first video
  prompt tools and extraction wizard are Phase 8 work.
- The UI does not yet preview video frames or edit masks; those review and
  correction surfaces arrive in later phases.
- `python` is unavailable on this machine; documented test commands use
  `python3`.

## Follow-Up Tasks

- Phase 8: add the video viewer, point/box/mask/label/keyframe prompt tools,
  and goal-first extraction wizard.
- Later UI phases: add review/correction tools, object-track inspection, export
  packaging controls, and richer artifact previews.
