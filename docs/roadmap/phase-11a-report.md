---
historical: true
default_context: false
---

# Phase 11A Report: Text-Guided Discovery Workflow

Date: 2026-05-17

## Summary

Phase 11A makes the existing CPU/mock text-guided discovery workflow runnable
from the local UI worker. A `Find objects from text` UI run now preserves the
validated run config in the backend job payload, routes mock `text_detector`
discovery through the shared multi-object pipeline, writes `candidates.json`,
adapts generated candidate mask sequences into object specs, and produces
normal track/export review artifacts.

The local UI review rail now has a Candidates panel sourced from
`review.candidateSummary`, so labels, candidate IDs, boxes, scores, sources,
and mask-handoff status are visible before users make track/export decisions.
Real open-vocabulary detector execution remains optional and capability-gated;
the worker requires `discovery.config.mock=true` for this UI text path and
continues to surface missing detector/model diagnostics instead of pretending
real detection is installed.

The working tree was not clean at phase start because
`docs/MOTIONJSON_CODEX_FUTURE_PLAN.md` and
`docs/Codex Prompt Instrcution.md` were preexisting untracked docs. They were
not staged for this phase.

## Changed Files

- `src/motionjson/backend/jobs.py`
  - Allows extract jobs to retain a normalized `run_config` payload.
- `src/motionjson/ui/server.py`
  - Stores the validated local UI run config when enqueueing extraction jobs.
- `src/motionjson/backend/worker.py`
  - Parses stored run configs, preserves runtime-safe input/output paths in
    job artifacts, and routes mock `text_detector` jobs through
    `run_multi_object_pipeline`.
- `src/motionjson/ui/static/index.html`
  - Adds the Candidates review panel.
- `src/motionjson/ui/static/app.js`
  - Renders `candidateSummary` rows with source, geometry, score, and
    mask-handoff status.
- `src/motionjson/ui/static/config_builder.js`
  - Marks generated text-detector configs as mock-capable for no-model UI
    smoke runs.
- `scripts/build_ui_shell.mjs`
  - Adds static checks for the Candidates panel and renderer.
- `scripts/test_ui_config_builder.mjs`
  - Locks the generated text-detector config to `mock: true`.
- `tests/test_phase11a_text_guided_discovery.py`
  - Adds a UI-to-worker regression test for text-guided mock discovery and a
    failure-diagnostics regression test for non-mock detector requests, plus a
    static UI candidate-review check.
- `docs/discovery_providers.md`
  - Documents local UI text-detector mock execution and review behavior.
- `docs/local_ui.md`
  - Documents the mock text-discovery local worker path and remaining
    detector-gated boundaries.

## Tests Run

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_phase11a_text_guided_discovery.py -q`
  - Result: 3 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest tests/test_discovery_providers.py tests/test_local_ui_api.py tests/test_phase9_ui_job_review_smoke.py tests/test_phase8_ui_config_builder.py tests/test_capabilities.py -q`
  - Result: 58 passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson-11a-text-mock --discovery-provider text_detector --discovery-text "red ball . hand" --discovery-config '{"mock": true, "max_candidates": 2}' --mask-provider mock --max-frames 2 --min-area 1`
  - Result: passed; wrote `candidates.json`, two text-detector object tracks,
    and MotionJSON outputs.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend diagnostics --json`
  - Result: passed; `text_detector` remains `missing_dependency`/not runnable
    for real detection, with `mockAvailable: true`.
- `node scripts/build_ui_shell.mjs`
  - Result: passed.
- `node scripts/test_ui_config_builder.mjs`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
  - Result: passed.
- `npm test`
  - Result: 19 passed.
- `npm run lint`
  - Result: passed.
- `npm run build`
  - Result: passed.
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q`
  - Result: 264 passed.

## Screenshots And Demos Produced

No screenshots were produced. The phase produced a local CLI smoke output under
`/tmp/motionjson-11a-text-mock`, which was not committed.

## Review

Read-only scout audits identified the critical gap: CLI text discovery already
worked, but local UI jobs discarded discovery config and always ran the legacy
single-object worker path. The implementation addresses that gap for the
mock/no-model text workflow and adds UI review visibility for candidate
summaries.

## Known Limitations

- This phase does not wire a real open-vocabulary detector adapter such as
  GroundingDINO. Diagnostics still report the real provider as unavailable
  unless optional dependencies and model configuration are added later.
- The local UI worker still does not execute `motion_foreground`,
  `sam_auto_masks`, or `class_detector` jobs; those remain later Phase 11
  slices or CLI workflows.
- Candidate review is post-run in this slice. A future accept/reject gate
  before segmentation/tracking remains follow-up work.

## Follow-Up Tasks

- Add a concrete detector adapter once optional model-loading, device
  diagnostics, and tests can be kept dependency-gated.
- Add a candidate accept/reject step before segmentation for advanced review
  workflows.
- Continue Phase 11B with automatic object proposal review and filtering.
