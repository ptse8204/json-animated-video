# Phase 13 Report - Packaging and Onboarding Docs

## Summary

Phase 13 adds install profiles, first-run diagnostics, and runnable onboarding
paths for local MotionJSON adoption. Package metadata now declares optional
extras for the dependency-free UI surface, SAM2, detector families, hosted
segmentation, OpenRouter, and development checks while keeping heavyweight ML
dependencies out of the base install.

The local UI now includes a First Run checklist backed by provider capability
diagnostics. It reports base dependency readiness, local UI availability,
no-model smoke readiness, optional model setup, and FFmpeg/export status. The
UI capabilities route also accepts video/output probes for setup checks and
redacts queried local absolute paths from public API responses.

Docs now include a dedicated first-run guide with Bash and Windows PowerShell
examples, red-ball and multi-object tutorials, install extras, launch commands,
diagnostics, and failure guidance. Existing local UI, onboarding, discovery
provider, and multi-object docs were updated to point users toward the correct
workflow and to explain common provider failure modes.

The phase started from a dirty working tree. The unrelated dirty files were
pre-existing `README.md`, `out/demo/**`, `AGENTS_old.md`, `README_old.md`, and
generated `out/demo` preview/runtime artifacts; they were left unstaged and
untouched.

## Changed Files

- `pyproject.toml`
- `scripts/build_ui_shell.mjs`
- `src/motionjson/capabilities.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `tests/test_local_ui_api.py`
- `tests/test_phase13_packaging_onboarding.py`
- `docs/first_run.md`
- `docs/index.md`
- `docs/onboarding.md`
- `docs/local_ui.md`
- `docs/discovery_providers.md`
- `docs/multi_object_extraction.md`
- `docs/roadmap/phase-13-report.md`

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m py_compile src/motionjson/capabilities.py src/motionjson/ui/server.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase13_packaging_onboarding.py -q` (`4 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase13_packaging_onboarding.py tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_capabilities.py -q` (`19 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py::test_local_ui_api_health_capabilities_and_defaults_are_public tests/test_local_ui_api.py::test_local_ui_capabilities_redacts_windows_probe_paths tests/test_phase13_packaging_onboarding.py tests/test_capabilities.py -q` (`20 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests -k "phase13 or capabilities or cli_ui" -q` (`22 passed, 202 deselected`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_local_ui_api.py -q` (`20 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` (`224 passed`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json --video examples/demo_red_ball.mp4 --output-dir /tmp/motionjson-phase13-probe`
- `python -m motionjson.cli ui --help` failed because `python` is not available
  in this shell (`zsh:1: command not found: python`); the equivalent `python3`
  command above passed.
- `python3 -m build --wheel --outdir /tmp/motionjson-phase13-dist` failed
  because the local environment does not have the `build` module installed
  (`No module named build`); package metadata is validated by the TOML test and
  the `dev` extra now includes `build`.
- `node --check src/motionjson/ui/static/app.js`
- `npm run build`
- `npm test` (`19 passed`)
- `npm run lint`
- `git diff --check`

## Known Limitations

- The `ui` extra is intentionally empty because the current UI is dependency
  free and packaged as static files. It still gives users a stable install
  profile for future UI dependencies.
- Optional ML extras declare provider families, but users still need compatible
  model weights and environment variables for SAM2, detector, hosted, or
  OpenRouter workflows.
- The First Run checklist summarizes current diagnostics; it does not download
  models, install FFmpeg, or mutate the user environment.
- PowerShell examples cover the main first-run and tutorial paths, not every
  advanced CLI command in the docs tree.

## Follow-Up Tasks

- Add a lightweight packaging build job that installs the `dev` extra and runs
  `python3 -m build` in CI.
- Add UI affordances for passing selected video/output directories into
  diagnostics beyond the current default form probe.
- Add a browser smoke that verifies the First Run checklist renders expected
  rows from a mocked capability payload.
