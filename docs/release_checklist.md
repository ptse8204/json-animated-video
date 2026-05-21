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

## License And Release Status Gate

- Confirm a `LICENSE` file exists before publishing a reusable release,
  package, or commercial-use claim.
- If no `LICENSE` file exists, keep README, release notes, repository status,
  and issue templates clear that reuse, redistribution, and commercial rights
  are not granted yet.
- Confirm the release is described as a local-first release candidate, not a
  production hosted service or public marketplace.
- Use signed or protected release tags for release candidates when repository
  settings allow it.

## Known Limitations

Known limitations must be clear in the release notes, README, and migration
guide before tagging. Do not imply that optional SAM2, detector, hosted model,
or Remotion workflows are bundled when they are only configured or planned.

## Object Discovery Release Gate

- Confirm Clean discovery is the default first-run object discovery preset.
- Confirm Maximum Recall is labeled advanced, slower, noisier, and useful when
  Clean misses desired objects.
- Confirm Trace Everything is expert/experimental, capped, requires explicit
  cost/noise acknowledgement, and blocks export until review.
- Confirm API review payloads own candidates, tracks, diagnostics, correction
  history, artifacts, timeline markers, and export eligibility; the UI must not
  fabricate normal completed job outputs.
- Confirm selected-candidate tracking validates candidate IDs, tracks selected
  objects by default, and returns updated API review/artifact state.
- Confirm auto-discovered exports remain review-gated and validation messages
  explain how to unblock them.
- Confirm SAM2 automatic proposals stay optional and capability-gated behind
  package/checkpoint/config/device diagnostics.
- Confirm SAM3 local/hosted concept, exemplar, and higher-recall paths remain
  optional, capability-gated, and clearly separated from the CPU/mock default.
- Confirm hosted SAM2/SAM3-compatible providers require explicit cost/privacy
  opt-in before network tests or hosted runs, and secrets are redacted from
  diagnostics, screenshots, API responses, logs, and docs.

## Guided UI And Model Connector Release Gate

- Confirm the default Local UI path remains no-model/mock friendly and readable
  without CLI knowledge, raw JSON, or provider terminology.
- Confirm the first-run workflow starts with video/project setup, goal cards,
  human-readable run plans, provider/privacy status, review, correction, and
  export handoff.
- Confirm raw JSON/config previews remain available for technical users behind
  advanced disclosures.
- Confirm model connector routes default to deterministic fake/local behavior
  for tests and do not call hosted providers by default.
- Confirm the OpenAI planning connector is server-side only, treats model
  output as a proposed run plan, validates generated configs before enqueue,
  and routes segmentation/tracking through explicit CV providers.
- Confirm every hosted provider, including OpenAI/OpenRouter planning and
  hosted SAM-style providers, requires explicit hosted-call opt-in and
  per-request cost/privacy acknowledgement before network calls.
- Never put model API keys, bearer tokens, hosted endpoints with credentials,
  or provider secrets in browser code, API responses, diagnostics,
  screenshots, logs, exported settings, test fixtures, or phase reports.
- Confirm reviewed selected objects are the default export target for
  automatically discovered candidates.

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

## Screenshot Freshness And Layout Gate

Check that screenshot tooling is available:

```bash
python3 scripts/capture_docs_assets.py --check
```

Regenerate screenshots only when UI changes affect the documented surfaces:

```bash
python3 scripts/capture_docs_assets.py
```

For release-bound UI changes, capture the responsive Local UI matrix and keep
the evidence path in the phase report:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/<release-id>
```

The release matrix should include 390x844, 768x1024, 1024x768, 1366x768,
1440x900, and 1920x1080 when tooling supports them. Confirm no horizontal page
overflow, card/panel overlap, clipped primary button text, unreadably narrow
card columns, or dense default control walls.

Do not add fake screenshots. If a screenshot cannot be captured, document the
missing asset in `docs/assets/README_ASSETS.md`.

## Repository Security Settings

- Enable private vulnerability reporting before asking users to report security
  issues through GitHub.
- Enable GitHub secret scanning and push protection for the repository.
- Enable Dependabot alerts and grouped updates for Python, npm, GitHub Actions,
  and Docker manifests.
- Protect the default branch with required reviews and required CI checks for
  Python tests, docs links/assets checks, JavaScript tests/lint/build,
  packaging dry runs, and Docker smoke.
- Keep Codex or CI automation review-only unless a maintainer explicitly
  approves write permissions, package publishing, hosted provider calls, or
  release-tag creation.
- Keep issue templates current for bugs, provider setup failures, docs fixes,
  and feature requests; public templates must warn against posting secrets,
  private media, local database files, or full local paths.

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
