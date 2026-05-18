# Final QA and Release Report

## Release Scope

This report closes the MotionJSON local-first video object tracing roadmap in
`codex_tasks.yaml` through Phase 14. The release candidate supports CPU/no-model
first-run workflows, optional heavyweight ML providers behind capability
diagnostics, local UI project/job/review/export flows, raster fallback
diagnostics, and validated MotionJSON handoff artifacts.

Unrelated pre-existing worktree dirt remains outside the release scope:
`README.md`, `AGENTS_old.md`, `README_old.md`, and generated `out/demo/**`
artifacts were not staged for the phase commits or this report.

## Phase Commits

| Phase | Commit | Report |
| --- | --- | --- |
| 0 | `2d4c126 phase 0: map repository and codex guardrails` | `docs/roadmap/phase-0-report.md` |
| 1 | `0dc8c72 phase 1: add typed extraction run configuration` | `docs/roadmap/phase-1-report.md` |
| 2 | `7f46106 phase 2: add provider capability diagnostics` | `docs/roadmap/phase-2-report.md` |
| 3 | `a9c8fc6 phase 3: add extraction job and artifact model` | `docs/roadmap/phase-3-report.md` |
| 4 | `e8e9203 phase 4: refactor extraction into provider pipeline` | `docs/roadmap/phase-4-report.md` |
| 5 | `7991798 phase 5: add multi-object discovery providers` | `docs/roadmap/phase-5-report.md` |
| 6 | `42faae2 phase 6: add object tracks and fallback diagnostics` | `docs/roadmap/phase-6-report.md` |
| 7 | `1baed49 phase 7: add local ui shell and api server` | `docs/roadmap/phase-7-report.md` |
| 8 | `79a113a phase 8: add video prompt tools and extraction wizard` | `docs/roadmap/phase-8-report.md` |
| 9 | `79297f0 phase 9: add ui job execution and result review` | `docs/roadmap/phase-9-report.md` |
| 10 | `7e77319 phase 10: add track correction workflows` | `docs/roadmap/phase-10-correction-workflows-report.md` |
| 11 | `404b45d phase 11: add validated export workflows` | `docs/roadmap/phase-11-report.md` |
| 12 | `a46bbba phase 12: add evaluation fixtures and benchmarks` | `docs/roadmap/phase-12-benchmarks-report.md` |
| 13 | `629f7c8 phase 13: add packaging and onboarding docs` | `docs/roadmap/phase-13-report.md` |
| 14 | `3fc7451 phase 14: prepare ui multi-object tracing release candidate` | `docs/roadmap/phase-14-report.md` |

Current commercial-roadmap canonical reports use
`docs/roadmap/phase-10-report.md` for free hosted demo paths and
`docs/roadmap/phase-12-report.md` for the final public launch audit. The older
Phase 10 correction and Phase 12 benchmark reports from a previous roadmap are
preserved under more specific filenames in the table above.

## Final Checks

Latest release-candidate checks recorded during Phase 14:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed,
  227 tests.
- `npm test -- --test-reporter=spec` - passed, 19 tests.
- `npm run lint` - passed.
- `npm run build` - passed.
- `node --check src/motionjson/ui/static/app.js` - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help` -
  passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
  - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
  - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli ui --help`
  - passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json`
  - passed and reported missing optional SAM2, hosted, detector, and OpenRouter
  providers without breaking base CLI use.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli benchmark --fixtures whole_frame_regression --modes external --out /tmp/motionjson-phase14-benchmark --width 64 --height 48 --frames 4`
  - passed; 1 run, 1 passed, 0 regressed, 0 failed.
- `git diff --check` - passed.

Post-review doc/header fixes also passed:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_phase14_release_candidate.py tests/test_local_ui_api.py::test_local_ui_serves_static_shell`
  - passed, 3 tests.
- `npm run build` - passed.
- `git diff --check` - passed.

## Manual Verification

- Launched the local UI in mock mode with:
  `python3 -m motionjson.cli ui --no-open --mock --host 127.0.0.1 --port 8767 --db /tmp/motionjson-phase14-ui.sqlite --storage-root /tmp/motionjson-phase14-ui-storage`.
- Verified the UI reported `API ready`, local health, no-model first-run
  checklist rows, focus CSS, skip-link wiring, and no horizontal overflow at
  the default browser viewport.
- Created a local project, registered `examples/demo_red_ball.mp4`, started a
  mock extraction run, and observed a `succeeded` job with one review track.
- Validated the export preset in the UI and generated export artifacts.
- Confirmed export links used local `/api/artifacts/.../content` routes.
- Stopped the temporary UI server after the smoke run.

## Known Limitations

- `python` is not installed in this shell; documented fallback commands use
  `python3` and passed.
- Job cancellation is cooperative. Pending local UI jobs cancel immediately;
  running jobs report `cancel_requested` until a worker reaches a cancellation
  check.
- Heavy ML providers are optional and not bundled by default. Missing SAM2,
  CUDA, hosted endpoints, detectors, model weights, and OpenRouter credentials
  are surfaced in diagnostics.
- The dependency-light local UI server is suitable for local-first inspection
  and smoke testing, but it is not a production streaming server for large
  videos.
- Browser smoke covered the local mock extraction/export workflow. Broader
  viewport, screen-reader, and real-provider QA remains manual.
- Real SAM2/text/class detector workflows require user-provided dependencies,
  model paths, and provider configuration.

## Release Decision

The Phase 0 through Phase 14 roadmap in `codex_tasks.yaml` is implemented with
phase reports and phase commits. The final release candidate is acceptable for
local CPU/no-model smoke use, validated MotionJSON export, and optional-provider
diagnostic onboarding, subject to the known limitations above.
