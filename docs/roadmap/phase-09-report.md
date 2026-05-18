# Phase 09 Report: CI, Packaging, And Release Readiness

Date: 2026-05-17

## Summary

Phase 09 added the missing release-readiness surface for contributors and CI.
The repository now has a GitHub Actions workflow that covers Python tests,
docs link/readiness checks, CLI smoke, Python package build, JavaScript
runtime/SDK tests, offline lint, static UI build smoke, npm workspace dry-pack
runs, Docker build smoke, container diagnostics, and `docker compose config`.

Root contributor files now exist: `CONTRIBUTING.md`, `SECURITY.md`, and
`CHANGELOG.md`. A new `docs/release_checklist.md` covers version bumps, tests,
docs screenshots, changelog/release notes, Python and npm package builds,
Docker build/run smoke, generated output policy, and known limitations.

Generated-output policy is now encoded in `.gitignore`: ad hoc `out/*` runs,
`.motionjson/`, `output/`, env files, local databases, logs, and build outputs
are ignored, while the intentionally checked-in `out/demo/**` fixture remains
available. Python and npm package metadata now include release-oriented
repository/readme/package fields without claiming a license the repository does
not yet have.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, `docs/Codex Prompt Instrcution.md`,
`.motionjson/`, and `out/demo_red_ball/` existed as untracked local/generated
artifacts. `.motionjson/` and `out/demo_red_ball/` are now ignored by policy;
the two untracked docs remain unstaged because they predate and are outside
this phase.

## Changed Files

- `.github/workflows/ci.yml`
  - Adds CI jobs for Python/docs/CLI/package build, JavaScript tests/lint/build
    and package dry-runs, plus Docker build/run/compose smoke.
- `.gitignore`
  - Ignores generated local state and output folders while preserving the
    tracked `out/demo/**` fixture exception.
- `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md`
  - Adds root contributor, security, and changelog entry points.
- `docs/release_checklist.md`
  - Adds the release checklist required by the future plan.
- `README.md`, `docs/index.md`, `docs/release_notes.md`, `docs/repo_status.md`
  - Link release/contributor docs, update release gates, and record generated
    output plus repo metadata policy.
- `pyproject.toml`
  - Adds `readme` and project URL metadata.
- `packages/motionjson-runtime/package.json`,
  `packages/motionjson-sdk/package.json`
  - Adds homepage/repository/bugs metadata and `files: ["src"]` package
    allowlists.
- `tests/test_phase09_release_readiness.py`
  - Adds CI-safe assertions for workflow coverage, package versions/metadata,
    release docs, generated-output ignores, and repo metadata recommendations.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_phase09_release_readiness.py tests/test_docs_links.py -q`
  - Result: 10 passed.
- `npm --workspace @motionjson/runtime run test`
  - Result: 13 passed.
- `npm --workspace @motionjson/sdk run test`
  - Result: 5 passed.
- `npm pack --dry-run --workspace @motionjson/runtime`
  - Result: passed; tarball includes package metadata and `src` files only.
- `npm pack --dry-run --workspace @motionjson/sdk`
  - Result: passed; tarball includes package metadata and `src` files only.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `python3 scripts/capture_docs_assets.py --check`
  - Result: passed; Chrome is available for screenshot capture.
- `docker compose config`
  - Result: passed.
- `python3 -m pip install -e ".[dev]"`
  - Result: passed; installed `build` and `wheel` needed for local package
    build validation.
- `python3 -m build --sdist --wheel --outdir /tmp/motionjson-phase09-dist`
  - Result: passed after the dev extra install.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
  and `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
  - Result: passed.
- `docker build -t motionjson-ci .`
  - Result: passed.
- `docker run --rm motionjson-ci python -m motionjson.cli backend diagnostics --json`
  - Result: passed; no-model providers were runnable and optional ML/provider
    gaps were reported as unavailable or not configured.
- `git diff --check`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q`
  - Result: 257 passed.

An initial local `python3 -m build --sdist --wheel` attempt failed with
`No module named build` before installing the dev extra. The CI workflow and
release checklist now install or require the dev extra before package build.

## Screenshots And Demos Produced

No new screenshots or demos were produced. Phase 09 added CI-safe screenshot
availability checks through `scripts/capture_docs_assets.py --check`; actual
screenshot regeneration remains an explicit docs maintenance step.

## Review

Read-only explorer subagents identified the primary gaps: no GitHub Actions
workflow, incomplete generated-output policy, missing root contributor/security
changelog files, missing release checklist, and thin package metadata. The
implementation addresses those gaps. Final reviewer passed the change with no
blocking findings and reminded that only intended Phase 09 files should be
staged, leaving the preexisting untracked docs out of the commit.

## Known Limitations

- The GitHub Actions workflow has not run on GitHub yet; it is validated by
  local command parity and file-level regression tests.
- The repository still has no license file, so release metadata intentionally
  does not claim a license.
- Python source distributions currently include tests through setuptools'
  default discovery. The wheel contains package code and package data only.
- Docker validation was local to Docker Desktop on this machine, not a remote
  Linux CI runner.

## Follow-Up Tasks

- Run the new workflow on GitHub and adjust if hosted runner differences appear.
- Decide whether Python sdists should exclude tests before public package
  publication.
- Add a license file before publishing packages or inviting redistribution.
- Keep `CHANGELOG.md` and `docs/release_notes.md` synchronized for the first
  real tag.

## 2026-05-18 Revalidation

Phase 09 was rechecked after the runtime embed smoke was added in Phase 08. The
GitHub Actions JavaScript job and release checklist now include
`npm run embed:smoke`, so CI/release gates cover the plain JavaScript website
embed in a real browser when Chrome is available. The Phase 09 readiness test
now asserts that command in both workflow and checklist coverage.
