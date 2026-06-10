---
historical: true
default_context: false
---

# Phase 04 Report: Documentation Information Architecture

Date: 2026-05-16

## Summary

Phase 04 turned the docs index from a flat release-document list into an
intent-based manual. The new entry points guide users by what they want to do:
try MotionJSON locally, extract objects, build website embeds, develop
providers, or continue with Codex.

The phase also added dedicated troubleshooting, glossary, and examples pages,
then added a scoped Markdown link test for the README and core docs spine.

The working tree was not clean at phase start because `.motionjson/`,
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md`, and `out/demo_red_ball/` were already
untracked local/generated artifacts. They were not staged for this phase.

## Changed Files

- `README.md`
  - Links to the new troubleshooting, examples, and glossary pages.
- `docs/index.md`
  - Rewritten around user intent:
    - try locally;
    - extract an object from video;
    - build a website embed;
    - develop providers;
    - use Codex to contribute.
- `docs/troubleshooting.md`
  - Adds setup, provider, bad-mask, and raster-only troubleshooting.
- `docs/glossary.md`
  - Adds short definitions for core MotionJSON terms.
- `docs/examples.md`
  - Adds red-ball, local UI, multi-object, browser preview, and website embed
    examples with expected output folders and real screenshots.
- `docs/repo_status.md`
  - Updates the documentation information architecture status.
- `tests/test_docs_links.py`
  - Adds CPU-safe checks for required docs pages, README/index cross-links,
    local Markdown link resolution, and repo-bound local links.

## Tests Run

- `python3 -m pytest -q tests/test_docs_links.py`
  - Result: 4 passed.
- `python3 -m pytest -q tests/test_docs_links.py tests/test_phase13_packaging_onboarding.py tests/test_phase14_release_candidate.py tests/test_ga_launch_docs.py`
  - Result: 18 passed.
- `python3 -m pytest -q`
  - Result: 236 passed.
- `npm run build`
- `npm test`
  - Result: 19 passed.
- `npm run lint`
- `git diff --check`

## Screenshots And Demos Produced

No new screenshots or demo assets were produced in Phase 04. The examples page
uses the real assets generated in Phase 03:

- `docs/assets/local-ui-first-run.png`
- `docs/assets/local-ui-new-project.png`
- `docs/assets/local-ui-extraction-wizard.png`
- `docs/assets/local-ui-provider-diagnostics.png`
- `docs/assets/local-ui-job-review.png`
- `docs/assets/canvas-preview-red-ball.png`
- `docs/assets/red-ball-demo.gif`

## Known Limitations

- The link test intentionally scans the core docs spine, not every historical
  roadmap report or copied Codex planning packet.
- Markdown anchor validation is deferred; the test verifies target files and
  repo-bound local paths.
- Troubleshooting centralizes current known failure modes, but provider-specific
  details should keep evolving in Phase 05 and Phase 06.

## Follow-Up Tasks

- Phase 05 should keep CLI/UI diagnostics language aligned with
  `docs/troubleshooting.md`.
- Phase 06 should expand provider-specific docs with local/free, GPU, model
  weight, and failure-mode fields.
- Phase 09 should decide generated-output ignore policy for local run artifacts.

## 2026-05-18 Revalidation

After Phase 03B added Local UI provider key and model settings, Phase 04 was
rechecked from a clean working tree. The docs spine now includes
`docs/security/api_keys.md` in the scoped link test, and that page includes a
real provider-settings screenshot from the Phase 03B layout matrix.
