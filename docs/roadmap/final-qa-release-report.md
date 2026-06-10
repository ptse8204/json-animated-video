# Final QA and Release Report

## Release Scope

MotionJSON is a local-first release candidate for turning selected video objects into reusable JSON-controlled motion layers. The safe first path is the no-model Local UI or red-ball CLI demo. Heavy ML and hosted providers remain optional and capability-gated.

Historical Phase 0-14 reports were removed from the working tree in `DOC-HARNESS-01`; git history preserves the full reports. See `docs/archive/phase_reports/README.md`.

## Phase Commit Summary

Original Phase 0-14 work produced typed run configs, provider diagnostics, job/artifact models, provider abstractions, object discovery, track filtering, Local UI/API, review/correction/export, benchmark fixtures, onboarding docs, and release-candidate hardening.

Recorded phase commits: `2d4c126`, `0dc8c72`, `7f46106`, `a9c8fc6`, `e8e9203`, `7991798`, `42faae2`, `1baed49`, `79a113a`, `79297f0`, `7e77319`, `404b45d`, `a46bbba`, `629f7c8`, `3fc7451`.

## Final Checks

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q` - passed, 227 tests.
- `npm test -- --test-reporter=spec` - passed, 19 tests.
- `npm run lint` - passed.
- `npm run build` - passed.
- `node --check src/motionjson/ui/static/app.js` - passed.
- `python3 -m motionjson.cli --help` - passed.
- `python3 -m motionjson.cli extract --help` - passed.
- `python3 -m motionjson.cli backend --help` - passed.
- `python3 -m motionjson.cli ui --help` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed and reported missing optional providers without breaking base CLI use.
- `python3 -m motionjson.cli benchmark --fixtures whole_frame_regression --modes external --out /tmp/motionjson-phase14-benchmark --width 64 --height 48 --frames 4` - passed.
- `git diff --check` - passed.

## Manual Verification

- Launched local UI in mock mode.
- Verified health/readiness, no-model checklist, focus styles, skip-link wiring, and no horizontal overflow at the default browser viewport.
- Created a project, registered `examples/demo_red_ball.mp4`, started a mock extraction, observed a succeeded job with one review track, validated export, and confirmed local `/api/artifacts/.../content` routes.

## Known Limitations

- Heavy ML providers are optional and not bundled by default.
- Missing SAM2, CUDA, hosted endpoints, detectors, model weights, and OpenRouter credentials are diagnostics, not base-install failures.
- Job cancellation is cooperative.
- The Local UI server is for local review, not production streaming of large videos.
- Real SAM2/text/class detector workflows need user-provided dependencies, model paths, and provider configuration.

## Release Decision

Acceptable for local CPU/no-model smoke use, validated MotionJSON export, and optional-provider diagnostic onboarding, subject to the known limitations.
