---
historical: true
default_context: false
---

# Phase OD-12 Report - Timeline Authoring And Preview

## Summary

Phase OD-12 adds an API-owned review timeline for object discovery and track
review. Local and authenticated review routes now include
`review.timeline` with candidate markers, track start/end/loss markers, marker
counts, and suggested keyframes. The local UI renders that API timeline in the
preview workspace, lets users apply suggested keyframes back into the next
discovery config, and keeps local keyframes visually separate from API review
markers.

Preview scrub behavior now avoids drawing API tracks outside their reported
visible frame range. Timeline marker clicks seek the preview and select related
tracks so the existing correction affordances for relabel, hide/show, export
inclusion, merge, split, add-object, and repair are easier to reach.

## Changed Files

- `src/motionjson/review_timeline.py`
  - Adds the shared `motionjson.review_timeline.v0.1` payload builder.
- `src/motionjson/ui/server.py`
  - Adds `review.timeline` to local UI artifact/review responses after
    correction state is applied.
- `src/motionjson/backend/api.py`
  - Adds the same timeline payload to authenticated `/v1/jobs/JOB_ID/review`.
- `src/motionjson/ui/static/index.html`, `app.js`, and `app.css`
  - Adds the preview timeline marker strip, suggested-keyframe control,
    marker list, scrub-safe overlay selection, and API timeline rendering.
- `src/motionjson/ui/static/config_builder.js`
  - Carries selected keyframes into API-first object discovery configs.
- `scripts/build_ui_shell.mjs` and `scripts/test_ui_config_builder.mjs`
  - Extends static UI contract checks for timeline affordances.
- `tests/test_review_timeline.py`, `tests/test_local_ui_api.py`,
  `tests/test_backend_api_product.py`
  - Covers timeline payload shape, marker counts, suggested keyframes, and
    public review responses.
- `README.md`, `docs/local_ui.md`, `docs/discovery_providers.md`
  - Documents the review timeline and API-first preview behavior.

## Tests Run

- `python3 -m py_compile src/motionjson/review_timeline.py src/motionjson/ui/server.py src/motionjson/backend/api.py`
- `python3 -m pytest tests/test_review_timeline.py tests/test_local_ui_api.py::test_local_ui_review_returns_api_first_candidates_and_redacts_private_fields tests/test_local_ui_api.py::test_local_ui_auto_object_proposals_mock_review_uses_artifact_backed_candidates tests/test_backend_api_product.py::test_rest_api_job_review_returns_api_first_candidate_payload -q`
- `node scripts/build_ui_shell.mjs`
- `python3 -m pytest tests/test_phase8_ui_config_builder.py tests/test_phase9_ui_job_review_smoke.py tests/test_phase03a_local_ui_layout.py::test_phase03a_layout_check_reports_viewport_matrix -q`
- `npm test`
- `python3 -m pytest -q`
- `npm run lint`
- `npm run build`
- Browser smoke against `python3 -m motionjson.cli ui --no-open --mock`: seeded a mock job, opened the local UI, verified API timeline marker rows and no horizontal overflow.
- `npm run ui:layout -- --check`
- `npm run ui:layout -- --state real-empty-shell,job-review --viewport laptop-1366,tablet-1024`
- `npm run embed:smoke`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m motionjson.cli benchmark --help`
- `python3 -m motionjson.cli backend diagnostics --json`
- `git diff --check`

## Risk Review

The requested read-only `rendering-scout` could not be spawned because the
Codex environment reported `agent thread limit reached`. The master agent
performed the rendering review in-thread and validated with browser smoke plus
layout checks. The partial real layout run passed but emitted a Python
`resource_tracker` warning for one leaked semaphore during shutdown; this did
not fail the layout command and appears to come from the smoke job process
cleanup path.

## Known Limitations

- The timeline uses review artifacts and configured discovery keyframes. It
  does not run a separate scene-change detector in the browser.
- Suggested keyframes are bounded to the first 12 unique review/config frames
  to keep the UI compact.
- The UI still needs an explicit "review approved" transition in a later phase
  to clear auto-discovery export review gates.

## Follow-up Tasks

- Add a backend scene-change detector or persisted scene-change artifact when
  the worker has a cheap CPU-safe implementation available.
- Extend the selected-object review workflow with a dedicated approval action
  that clears `review_pending` after user review.
