# Phase 4 Browser E2E Report

## Summary

Phase 4 adds a real browser E2E suite for the Local UI using the repository's dependency-free Chrome/CDP pattern instead of adding Playwright. The suite starts `motionjson ui` in debug mock mode with a temporary SQLite database and storage root, drives Chrome through the guided workflow, records page errors and network violations, and skips with diagnostics when Chrome is unavailable unless `MOTIONJSON_E2E_REQUIRED=1`.

Covered journeys:

- first load of the guided local UI;
- mobile 390x844 first-load control visibility;
- mock/no-model run creation, review correction, export validation, and export handoff URL checks;
- hosted SAM3 setup blocker, hosted opt-in persistence, fake key redaction, and no smoke/setup job calls during save;
- model-plan API failure rendered in the UI without creating a job;
- fake-local model planning with no extraction job until the user clicks Confirm and start.

The browser suite exposed a real preview-path issue: review asset preloading attempted raw `masks/...` files through the safe preview route, which the server intentionally blocks. The UI now preloads only allowed review frame assets.

## Changed Files

- `package.json` - adds `npm run test:e2e`.
- `scripts/test_local_ui_e2e.mjs` - adds the browser E2E harness and scenarios.
- `src/motionjson/ui/static/app.js` - stops preloading blocked raw mask paths through `/api/jobs/{jobId}/preview-files`.
- `docs/roadmap/phase-4-browser-e2e-report.md` - this report.

## Browser Evidence

The phase uses automated rendered browser evidence rather than committed screenshots. `npm run test:e2e` opens the Local UI in headless Chrome against a live local server, drives DOM interactions, captures console exceptions, records network requests, asserts no external browser requests, and fails on failed preview-file requests. No screenshots were committed because this phase did not change layout; targeted layout smoke checks still ran for mobile and laptop states.

The in-app Browser plugin was not exposed as a committed test dependency, and Playwright is not installed in this repository. The suite uses direct Chrome/CDP like `scripts/check_local_ui_layout.mjs` so it can run locally and in CI without new frontend dependencies.

## Tests Run

- `npm run test:e2e` - 7 passed.
- `npm test` - 23 passed.
- `npm run build`.
- `npm run lint`.
- `python3 -m pytest tests/test_local_ui_api.py tests/test_local_ui_workflow_matrix.py tests/test_provider_registry.py tests/test_local_ui_model_connectors.py -q` - 87 passed.
- `npm run ui:layout -- --state workflow-goal --viewport mobile-390`.
- `npm run ui:layout -- --state workflow-provider --viewport laptop-1366`.
- `python3 -m motionjson.cli --help`.
- `python3 -m motionjson.cli extract --help`.
- `python3 -m motionjson.cli backend --help`.
- `git diff --check`.

## Scout Review

Used one read-only `test-gap-scout`. Material recommendations were incorporated:

- required-browser mode with `MOTIONJSON_E2E_REQUIRED=1`;
- browser network recording and failed preview-file assertions;
- hosted secret redaction assertions;
- UI-rendered model-planning failure coverage;
- mobile first-load smoke coverage;
- UI confirmation click for the model-plan success path.

## Known Limitations

- Browser E2E tests skip when Chrome/Chromium is unavailable unless `MOTIONJSON_E2E_REQUIRED=1`.
- The suite does not use hosted providers, GPU providers, model downloads, or external network access.
- Python's local HTTP server can print `BrokenPipeError` traces when headless Chrome closes a page with in-flight requests; the E2E assertions still pass and no provider failure is hidden.

## Follow-up Tasks

- Add CI wiring that runs `npm run test:e2e` with `MOTIONJSON_E2E_REQUIRED=1` on an image with Chrome installed.
- Consider teaching the local UI server to suppress benign client-disconnect tracebacks while preserving provider/runtime failure diagnostics.
