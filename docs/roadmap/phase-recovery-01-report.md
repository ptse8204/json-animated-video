---
historical: true
default_context: false
---

# Phase RECOVERY-01 Report - Truthful Readiness And Effort Controls

## Summary

Implemented the first recovery slice for truthful completion and review readiness. Extraction now separates worker completion from review/tool readiness, exposes a backend review-tools contract, carries run-level runtime proof into the selected-run UI, and adds guided Fast/Balanced/High quality effort settings that map to real run config fields.

## Changed Files

- `src/motionjson/backend/readiness.py`
  - Added shared readiness and review-tool status helpers.
- `src/motionjson/backend/worker.py`
  - Emits `worker_complete`, `artifacts_registered`, `review_payload_ready`, `preview_tools_ready`, `ready_for_review`, and `readiness_blocked`.
  - Registers artifacts before success, stores readiness/runtime proof in the queue result, and caps terminal progress at 99% when readiness is blocked.
  - Enforces CUDA runtime proof after SAM3 runtime warmup is verified.
- `src/motionjson/job_artifacts.py`
  - Allows success events to report a caller-provided progress ratio for finalizing states.
- `src/motionjson/backend/job_lifecycle.py`
  - Adds `finalizing_review` lifecycle status, readiness-aware actions, GPU mismatch failure copy, and progress capping.
- `src/motionjson/ui/server.py`
  - Adds `/api/jobs/{jobId}/review-tools` and attaches readiness to public job snapshots.
- `src/motionjson/ui/static/app.js`
  - Displays runtime proof/readiness, gates review tools on backend readiness, improves review primary actions, and adds effort-aware config generation.
- `src/motionjson/ui/static/ui_selectors.js`
  - Adds effort preset defaults and adaptive chips for effort/refinement.
- `src/motionjson/ui/static/config_builder.js`
  - Keeps standalone config generation aligned with effort presets.
- `src/motionjson/ui/static/index.html`
  - Adds the guided effort control and platform-neutral copy updates.
- `scripts/test_ui_config_builder.mjs`
  - Covers review-tools route exposure, effort mapping, runtime badge, readiness gate, and static fallback review actions.
- `tests/test_backend_jobs_worker.py`
  - Covers readiness events/results and CUDA proof mismatch.
- `tests/test_job_lifecycle.py`
  - Covers finalizing review assets and SAM3 Scene Sweep provider label.
- `tests/test_local_ui_api.py`
  - Covers review-tools readiness and no demo handoff URL.

## Tests Run

- `python3 -m pytest -q tests/test_provider_settings.py tests/test_capabilities.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py tests/test_final_export.py tests/test_track_filtering.py tests/test_job_lifecycle.py`
  - Result: passed, 170 tests.
- `npm test`
  - Result: passed, 21 node tests.
- `npm run build`
  - Result: passed.
- `python3 -m motionjson.cli --help`
  - Result: passed.
- `python3 -m motionjson.cli extract --help`
  - Result: passed.
- `git diff --check`
  - Result: passed.

## Known Limitations

- This phase does not rebuild the desktop review workbench layout; no browser screenshot evidence was required for this backend/product-state slice.
- Candidate-first materialization and full mask-quality scoring remain follow-up phases.
- Runtime proof is now carried per run when a runtime contract is available. CPU/mock/no-model runs still report unverified or no runtime proof, as expected.
- Review tools are gated by artifact presence, but individual tool internals still need the later workbench/tool pass to improve review editing UX.

## Follow-Up Tasks

- Implement candidate-first SAM3 scene sweep with accepted/rejected candidate materialization boundaries.
- Add mask quality scoring and make rough/static fallback tracks diagnostic-only by default in backend metadata.
- Rebuild the desktop review workbench with rendered screenshot gates.
- Extend review tool internals so keep/reject/export inclusion, repair prompts, and real artifact handoff are usable end to end.
