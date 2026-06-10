---
historical: true
default_context: false
---

# Phase 14 Report - Release Candidate Polish

## Summary

Phase 14 prepares the local multi-object tracing workflow for a release
candidate. The implementation adds focused local UI accessibility and keyboard
polish, cooperative cancellation from the local UI API, local-only dynamic
content link guards, no-store headers for UI/API responses, release notes,
migration and known-limitation documentation, and release-candidate QA gates.

The browser smoke launched the local UI in mock mode on `127.0.0.1`, created a
project, registered `examples/demo_red_ball.mp4`, started a mock run, observed a
succeeded run with one review track, validated export, and generated local
export artifacts through `/api/artifacts/.../content` links.

## Changed Files

- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/build_ui_shell.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_local_ui_api.py`
- `tests/test_phase14_release_candidate.py`
- `docs/index.md`
- `docs/local_ui.md`
- `docs/codex_motionjson_quality_benchmarks.md`
- `docs/release_notes.md`
- `docs/migration_and_known_limitations.md`
- `docs/roadmap/phase-14-report.md`

## Tests Run

- `node --check src/motionjson/ui/static/app.js` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_local_ui_api.py::test_local_ui_serves_static_shell tests/test_local_ui_api.py::test_local_ui_cancel_pending_job_records_public_status_and_event tests/test_local_ui_api.py::test_local_ui_exports_valid_motionjson_from_corrected_review_state_and_imports_previous_result tests/test_phase14_release_candidate.py` - passed, 6 tests.
- `npm test -- --test-reporter=spec` - passed, 19 tests.
- `npm run build` - passed.
- `npm run lint` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json` - passed.
- Browser smoke against `python3 -m motionjson.cli ui --no-open --mock --host 127.0.0.1 --port 8767 --db /tmp/motionjson-phase14-ui.sqlite --storage-root /tmp/motionjson-phase14-ui-storage` - passed; temporary server was stopped manually after the smoke.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 227 tests.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures whole_frame_regression --modes external --out /tmp/motionjson-phase14-benchmark --width 64 --height 48 --frames 4` - passed; 1 run, 1 passed, 0 regressed.
- `git diff --check` - passed.
- Post-review fixes for the release docs and visible UI header:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_phase14_release_candidate.py tests/test_local_ui_api.py::test_local_ui_serves_static_shell` - passed, 3 tests; `npm run build` - passed; `git diff --check` - passed.

## Known Limitations

- Job cancellation is cooperative. Pending UI jobs cancel immediately; running
  worker jobs report `cancel_requested` until the next cancellation check.
- The dependency-light local UI server uses local no-store headers and range
  handling, but it is not a production streaming server for large media.
- Browser smoke verifies the static UI workflow and local API handoff, while
  broader viewport and assistive-technology review remains manual QA.
- Heavyweight providers remain optional. Missing SAM2, CUDA, hosted endpoints,
  detectors, and model weights are reported as diagnostics rather than installed
  by default.

## Follow-Up Tasks

- Add automated viewport browser checks for 390px, 920px, 1280px, and wide
  desktop when the test environment can run a browser reliably in CI.
- Add streaming storage reads for large artifact/video responses if the local UI
  server becomes a primary path for long-form video inspection.
- Expand browser smoke coverage for relabel/hide/delete interactions once the
  in-app browser fill path is reliable in this environment.
