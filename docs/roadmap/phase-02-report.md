# Phase 02 Report - First-run Scripts and Free Instance Docs

## Summary

Phase 02 added copy-pasteable first-run paths for local CPU/mock usage, a local
API launcher, red-ball demo automation, a Codespaces-oriented devcontainer, and
docs for local and free/low-install environments. Heavy ML providers remain
optional and diagnostics-first.

## Changed Files

- `.devcontainer/devcontainer.json`: Python 3.11 devcontainer with Node 22,
  FFmpeg/system libraries, CPU/mock environment defaults, forwarded API/UI
  ports, editable `.[ui,dev]` install, UI build, and diagnostics check.
- `scripts/first_run_local.sh`: one-script local setup for venv install,
  diagnostics, optional red-ball demo, and mock UI launch.
- `scripts/first_run_local.ps1`: PowerShell equivalent for Windows users.
- `scripts/run_local_ui_mock.sh`: starts the local UI in no-model mock mode.
- `scripts/run_red_ball_demo.sh`: generates, extracts, and validates the
  deterministic red-ball demo.
- `scripts/run_backend_api.sh`: initializes and serves the dependency-light
  local backend API.
- `docs/run_local.md`: local setup guide covering venv install, mock UI,
  red-ball demo, local API, Docker, Compose, optional ML extras, and cleanup.
- `docs/run_free_instances.md`: Codespaces, Colab CLI demo, Hugging Face Space
  plan, privacy/persistence cautions, and official reference links.
- `README.md`: linked the one-script local path and new docs.
- `docs/index.md`: linked the new local/free-instance docs.

No runtime, backend, frontend, provider, schema, or package dependency behavior
was changed.

## Subagent Notes

- `docs_devrel_engineer`: recommended intent-based local/free docs, CPU/mock
  caveats, Colab as CLI-only, and no overclaiming of free GPU/hosted paths.
- `release_packaging_engineer`: recommended keeping defaults CPU/mock,
  hardening `--clean`, adding richer diagnostics to first-run, documenting API
  auth expectations, and adding devcontainer env defaults.

## Tests And Smoke Commands

- `bash -n scripts/first_run_local.sh scripts/run_local_ui_mock.sh scripts/run_red_ball_demo.sh scripts/run_backend_api.sh` - passed.
- `python3 -m json.tool .devcontainer/devcontainer.json >/dev/null` - passed.
- `scripts/first_run_local.sh --help` - passed.
- `scripts/run_local_ui_mock.sh --help` - passed.
- `scripts/run_red_ball_demo.sh --help` - passed.
- `scripts/run_backend_api.sh --help` - passed.
- `scripts/first_run_local.sh --no-launch --venv /tmp/motionjson-phase02-first-run-venv` - passed; created a temporary venv, installed `.[ui]`, and ran diagnostics with video/output checks.
- `scripts/first_run_local.sh --skip-install --no-launch --venv /tmp/nonexistent-motionjson-venv` - passed; used current `python3` and ran diagnostics with video/output checks.
- `scripts/run_red_ball_demo.sh --video /tmp/motionjson-phase02-red-ball.mp4 --out /tmp/motionjson-phase02-red-ball --clean` - passed; generated demo video, extracted 12 frames, and validation reported 8 MotionJSON files.
- `scripts/run_red_ball_demo.sh --out . --clean` and `scripts/run_red_ball_demo.sh --out .. --clean` - correctly refused dangerous clean paths with exit code 2.
- `scripts/run_backend_api.sh --db /tmp/motionjson-phase02-api/backend.sqlite --storage-root /tmp/motionjson-phase02-api/storage --init-only` - passed.
- `scripts/run_local_ui_mock.sh --db /tmp/motionjson-phase02-ui/backend.sqlite --storage-root /tmp/motionjson-phase02-ui/storage --host 127.0.0.1 --port 0` - passed startup smoke; `/api/health` returned `status: ok` and `/api/capabilities` reported 15 of 22 providers ready. The temporary server was stopped after the smoke check.
- `docker compose config` - passed.
- `python3 -m pytest -q tests/test_cli_ui.py tests/test_phase13_packaging_onboarding.py tests/test_ga_launch_docs.py` - passed, 13 tests.
- `npm run build` - passed.
- `npm test` - passed, 19 Node tests.
- `npm run lint` - passed.

PowerShell script execution was not run because `pwsh`/`powershell` is not
installed in this environment. The script was reviewed and documented, but it
needs a Windows or PowerShell runner for execution coverage.

## Screenshots And Demos Produced

No README screenshots or GIF/MP4 demo assets were produced in Phase 02. The
red-ball script was smoke-tested against `/tmp` to avoid changing the existing
untracked `out/demo_red_ball/` worktree artifact.

## Known Limitations

- The first-run shell script performs a real editable install and can take time
  on fresh machines.
- Codespaces, Colab, and Hugging Face docs are conservative setup guidance, not
  proof of a production hosted demo.
- The devcontainer was JSON-validated but not built inside Codespaces during
  this phase.
- PowerShell execution still needs verification on a Windows/PowerShell host.
- Existing untracked `.motionjson/`, uppercase future-plan copy, and
  `out/demo_red_ball/` artifacts remain outside this phase commit scope.

## Review

Reviewer found two material issues: `run_red_ball_demo.sh --clean` allowed
cleanup outside intended generated-output areas, and the devcontainer readiness
claim was stronger than the actual build verification. The script now only
cleans repo-local `out/*` or `/tmp`/`/private/tmp` `motionjson-*` paths, the
devcontainer installs npm dependencies before `npm run build`, and the report
uses "Codespaces-oriented" instead of claiming a built Codespaces environment.
Re-review found no material findings.

## External References Checked

- GitHub Codespaces port forwarding documentation.
- Google Colab FAQ for managed-runtime restrictions and variable resource
  availability.
- Hugging Face Spaces overview, Docker Spaces docs, and Spaces storage docs for
  CPU Basic, secrets, Docker, and ephemeral storage guidance.

## Follow-Up Tasks

- Phase 03: automate real screenshot/demo capture and embed verified assets in
  the README.
- Phase 04: fold `docs/run_local.md` and `docs/run_free_instances.md` into the
  intent-based docs navigation.
- Phase 09/10: add CI/devcontainer validation and any committed Colab or
  Hugging Face Space artifacts.
