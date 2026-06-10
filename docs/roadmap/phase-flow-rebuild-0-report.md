---
historical: true
default_context: false
---

# Phase 0 Report - Local UI Flow Rebuild Baseline Audit

## Summary

Phase 0 audited the current Local UI and job orchestration behavior before
product code changes. The audit used the new rebuild prompt in
`docs/codex/codex_ui_flow_rebuild_prompt.md` as user-provided working context
and left product behavior unchanged.

The working tree was not clean at phase start because
`docs/codex/codex_ui_flow_rebuild_prompt.md` was already untracked. This report
records that file as pre-existing user context for the goal.

The current UI can launch in debug/no-model mode and the mock extraction path is
usable, but the baseline confirms the core product problem from the prompt:
workflow state, job state, failure state, review state, and next actions are
not represented by one authoritative lifecycle contract. Several UI states still
derive readiness from local frontend state and render contradictory blocked
reasons or incomplete failure guidance.

## Baseline Evidence

Screenshots were captured with the repository headless Chrome layout tool under:

```text
docs/design/screenshots/flow-rebuild-phase-0/
```

The captured matrix covers these viewports:

- `390x844`
- `768x1024`
- `1024x768`
- `1366x768`
- `1440x900`
- `1920x1080`

The captured states were:

- `workflow-goal`
- `workflow-video`
- `workflow-provider`
- `workflow-run`
- `workflow-review`
- `workflow-review-failure`
- `export-gate`
- `job-review`
- `model-setup`
- `prepare-sam3-single`

Representative files include:

- `docs/design/screenshots/flow-rebuild-phase-0/mobile-390-workflow-run.png`
- `docs/design/screenshots/flow-rebuild-phase-0/desktop-1440-workflow-run.png`
- `docs/design/screenshots/flow-rebuild-phase-0/mobile-390-workflow-review-failure-full.png`
- `docs/design/screenshots/flow-rebuild-phase-0/desktop-1440-job-review.png`
- `docs/design/screenshots/flow-rebuild-phase-0/desktop-1440-model-setup.png`

## Findings

- The visible flow still has competing concepts: older Setup/Prepare/Review
  language, the five-step guided flow, main goal cards, sidebar goal context,
  advanced panels, and right-rail state all compete for the user's attention.
- The headless layout gate failed in `workflow-run` because the prepare step can
  show a blocked footer reason while the run call to action is available. This
  makes the next action contradictory.
- The headless layout gate failed in `workflow-review-failure` because the
  failed post-run guide and logs/fallback diagnostics were not visible in the
  expected guided structure across all six viewports.
- `/api/jobs`, `/api/jobs/{jobId}`, and `/api/progress` currently return public
  job snapshots with scalar `progress`/`percent` and the latest event message,
  but not a normalized lifecycle object containing `phase`, known-vs-unknown
  progress, failure headline/reason/action, review summary, or action gates.
- `_public_job_snapshot` uses fallback precision for jobs without progress
  events: terminal jobs become `100`, running jobs become `25`, and other jobs
  become `0`. The rebuild needs `progress.known: false` instead of implying
  measured precision.
- Job state is still spread across job rows, events, artifacts, review payloads,
  correction state, frontend run configs, selected job state, and polling
  results.
- The frontend builds review tracks from backend review payloads when present,
  but can also generate `demo-only` non-exportable review estimates from config
  or count-only results for non-terminal jobs. Later phases should make these
  explicit preview estimates and keep them out of normal review/export truth.
- Provider readiness is visible in diagnostics. In this environment SAM2 and
  SAM3 local providers are unavailable because optional packages/model paths are
  missing, hosted providers need keys and explicit network opt-in, and no-model
  providers remain runnable.

## API And State Map

Setup and workspace state:

- `GET /api/health`
- `GET /api/workspace`
- `GET /api/commercial-readiness`
- `GET /api/capabilities`
- `GET /api/provider-settings`
- `GET /api/model-providers`
- `GET /api/run-config/defaults`
- `GET /api/exports/formats`
- `GET /api/projects`
- `GET /api/videos?projectId=...`

Plan and provider setup:

- `POST /api/provider-settings`
- `POST /api/provider-settings/{providerId}/diagnose`
- `POST /api/provider-settings/{providerId}/test`
- `POST /api/provider-settings/{providerId}/smoke-test`
- `POST /api/run-config/validate`
- `POST /api/model-runs`
- `GET /api/model-runs/{runId}`
- `GET /api/model-runs/{runId}/events`
- `POST /api/model-runs/{runId}/cancel`
- `POST /api/model-runs/{runId}/confirm-job`
- `POST /api/jobs/{jobId}/model-plan`

Job orchestration:

- `POST /api/jobs`
- `POST /api/jobs/{jobId}/run`
- `GET /api/jobs?projectId=...`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/events`
- `GET /api/progress?projectId=...`
- `POST /api/jobs/{jobId}/cancel`

Review, correction, and export:

- `GET /api/jobs/{jobId}/artifacts`
- `GET /api/jobs/{jobId}/review`
- `GET /api/jobs/{jobId}/corrections`
- `POST /api/jobs/{jobId}/track-selected`
- `POST /api/jobs/{jobId}/track-edits`
- `POST /api/jobs/{jobId}/validate`
- `POST /api/jobs/{jobId}/exports`
- `GET /api/artifacts?jobId=...`

## Changed Files

- `docs/roadmap/phase-flow-rebuild-0-report.md`
- `docs/design/screenshots/flow-rebuild-phase-0/*.png`

No product code was changed.

## Tests And Validation

- `python3 -m motionjson.cli --help` - passed.
- `python3 -m motionjson.cli backend diagnostics --json` - passed. The report
  showed no CUDA, missing optional SAM2/SAM3 packages/model paths, missing
  hosted provider keys, hosted network opt-in disabled, and runnable no-model
  providers.
- `python3 -m motionjson.cli ui --no-open --debug-mock --host 127.0.0.1 --port 0 --db /tmp/motionjson-phase0-ui.sqlite --storage-root /tmp/motionjson-phase0-storage` - launched successfully at a local random port, then was stopped with Ctrl-C after confirming startup.
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/flow-rebuild-phase-0 --state workflow-goal,workflow-video,workflow-provider,workflow-run,workflow-review,workflow-review-failure,export-gate,job-review,model-setup,prepare-sam3-single --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920` - failed as baseline evidence with the workflow-run and workflow-review-failure findings listed above.
- `npm test` - passed, 21 Node tests.
- `python3 -m pytest -q tests/test_cli_ui.py tests/test_local_ui_api.py tests/test_backend_jobs_worker.py` - passed, 47 tests.

## Known Limitations

- The layout command failure is intentionally recorded as baseline evidence,
  not introduced by this phase.
- The audit used repository-generated debug/mock states for several UI captures.
  Later implementation phases still need after-screenshots against the real
  updated UI states.
- The audit did not change backend API response shapes. Phase 1 must add the
  authoritative lifecycle contract while preserving existing fields.

## Follow-Up Tasks

- Add a backend lifecycle summary that normalizes job status, phase, progress,
  latest event, provider summary, failure summary, review summary, and available
  actions.
- Preserve current routes and fields while exposing the normalized lifecycle
  view through existing workspace/progress/job responses where possible.
- Replace scalar fallback progress with `known: false` when progress is not
  measured.
- Make failed/canceled jobs visible in recent jobs with recovery guidance.
- Move frontend job center and workflow gates to pure selectors that consume the
  normalized lifecycle state rather than DOM classes or scattered state.
