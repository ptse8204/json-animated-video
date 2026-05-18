# MotionJSON Release Checklist

Use this checklist before creating a release tag or asking users to rely on a
new build.

## Version And Notes

- Bump `pyproject.toml` and package versions in
  `packages/motionjson-runtime/package.json` and
  `packages/motionjson-sdk/package.json` when the release changes package
  behavior.
- Update `CHANGELOG.md`.
- Update `docs/release_notes.md`.
- Confirm `docs/migration_and_known_limitations.md` still states current known
  limitations, optional provider boundaries, and raster-only constraints.

## Known Limitations

Known limitations must be clear in the release notes, README, and migration
guide before tagging. Do not imply that optional SAM2, detector, hosted model,
or Remotion workflows are bundled when they are only configured or planned.

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q
npm test
npm run lint
npm run build
npm run embed:smoke
npm --workspace @motionjson/runtime run test
npm --workspace @motionjson/sdk run test
git diff --check
```

## Docs Screenshots

Check that screenshot tooling is available:

```bash
python3 scripts/capture_docs_assets.py --check
```

Regenerate screenshots only when UI changes affect the documented surfaces:

```bash
python3 scripts/capture_docs_assets.py
```

Do not add fake screenshots. If a screenshot cannot be captured, document the
missing asset in `docs/assets/README_ASSETS.md`.

## Package Build

Install the dev extra first if `python3 -m build` is unavailable:

```bash
python3 -m pip install -e ".[dev]"
```

```bash
python3 -m build --sdist --wheel
npm pack --dry-run --workspace @motionjson/runtime
npm pack --dry-run --workspace @motionjson/sdk
```

Confirm the runtime and SDK tarballs do not include private local data,
provider keys, or generated outputs outside intentional package contents.

## Docker Build

```bash
docker build -t motionjson-ga .
docker run --rm motionjson-ga python -m motionjson.cli backend diagnostics --json
docker compose config
```

Docker should build without optional ML dependencies. SAM2, detectors, hosted
segmentation, OpenRouter, and provider credentials must remain opt-in.

## Generated Output Policy

- Keep `.motionjson/`, `output/`, and ad hoc `out/<run>/` folders out of
  commits.
- Keep `out/demo/` tracked only as the intentional small runtime/web demo.
- Add new generated assets only when they are deterministic, documented, small
  enough for the repo, and required by tests or public docs.

## Final Review

- Read `README.md` as a first-time user.
- Confirm `CONTRIBUTING.md`, `SECURITY.md`, and `CHANGELOG.md` are current.
- Confirm CI is green for Python tests, docs link checks, JavaScript
  build/lint/tests, website embed smoke, package dry runs, and Docker build
  smoke.
- Confirm `docs/repo_status.md` still has current GitHub About, website,
  topics, and release-status recommendations.
