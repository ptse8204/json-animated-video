# Phase 08 Report: Runtime, SDK, And Website Embed Adoption

Date: 2026-05-17

## Summary

Phase 08 made the web-adoption path explicit for frontend developers. The
README now explains how to open the plain JavaScript embed against a generated
`web_asset_manifest.json`, when to use `web_asset_manifest.json` versus
`scene_graph.json`, how `@motionjson/runtime` differs from `@motionjson/sdk`,
how to validate the JavaScript workspaces, and what `website-zip` and
`remotion-plan` do today.

The runtime guide now documents supported web surfaces, output manifest
anatomy, package-local test and dry-pack commands, website ZIP contents, and
SDK orchestration boundaries. The developer API docs now cross-link SDK usage
back to the browser runtime guide.

The runtime and SDK workspaces now expose package-local `npm run test` scripts
so the documented test paths are real. A Phase 08 Python regression test keeps
the README, runtime guide, package metadata, local example, and committed demo
manifest aligned.

The working tree was not clean at phase start because `.motionjson/`,
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, `docs/Codex Prompt Instrcution.md`,
and `out/demo_red_ball/` were untracked local/generated artifacts. They were
not staged for this phase.

## Changed Files

- `README.md`
  - Adds a website adoption section with plain JS embed, runtime, SDK, manifest
    anatomy, website ZIP, and Remotion plan guidance.
- `docs/runtime.md`
  - Adds supported web format status, output manifest anatomy, package
    validation commands, website ZIP details, and SDK usage.
- `docs/developer_api.md`
  - Clarifies that the SDK is backend orchestration and links browser playback
    to the runtime guide.
- `packages/motionjson-runtime/package.json`
  - Adds a package-local test script.
- `packages/motionjson-sdk/package.json`
  - Adds a package-local test script.
- `tests/test_phase08_runtime_adoption.py`
  - Adds CI-safe assertions for docs, package metadata, local examples, and the
    demo web manifest.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_phase08_runtime_adoption.py -q`
  - Result: 4 passed.
- `npm --workspace @motionjson/runtime run test`
  - Result: 13 passed.
- `npm --workspace @motionjson/sdk run test`
  - Result: 5 passed.
- `npm pack --dry-run --workspace @motionjson/runtime`
  - Result: passed.
- `npm pack --dry-run --workspace @motionjson/sdk`
  - Result: passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider tests/test_phase08_runtime_adoption.py tests/test_final_export.py tests/test_docs_links.py tests/test_timeline_editor.py -q`
  - Result: 17 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=src python3 -m pytest -p no:cacheprovider -q`
  - Result: 251 passed.

## Screenshots And Demos Produced

No new screenshots were produced. The adoption path uses existing local demos:
`out/demo/web_asset_manifest.json`, the generated red-ball output path
documented in the README, and `examples/plain_js_embed.html`.

## Review

Explorer subagents confirmed the Phase 08 scope comes from the future plan and
identified the main gaps as README adoption coverage, missing package-local
test scripts, and lack of dedicated browser smoke. The implementation addresses
the README/package gaps and adds CI-safe doc/example/manifest coverage. A real
browser smoke remains a follow-up because current JavaScript validation is
Node/static and dependency-free.

## Known Limitations

- The runtime packages are still plain ESM source packages. `npm run build`
  validates the static UI shell; it does not generate a publishable runtime
  bundle.
- Browser example coverage remains static/CI-safe. There is no automated
  browser test that serves the examples, inspects console errors, and verifies
  rendered pixels.
- `remotion-plan` remains a JSON integration plan only. It does not install
  Remotion or generate a Remotion component.
- Website playback consumes cached raster/alpha assets and JSON transforms; it
  does not run segmentation, matting, detection, or hidden-pixel reconstruction.

## Follow-Up Tasks

- Add a dependency-gated browser smoke that serves `examples/plain_js_embed.html`
  and verifies manifest fetch, mount success, no console errors, and nonblank
  render output.
- Decide whether published npm packages should include tests in tarballs or use
  a `files` allowlist before external package publication.
- Implement a real Remotion adapter only when the project is ready to own the
  dependency, generated component shape, and docs/tests.
