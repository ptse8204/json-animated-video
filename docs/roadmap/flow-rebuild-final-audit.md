---
historical: true
default_context: false
---

# Local UI Flow Rebuild Final Audit

## Summary

The flow rebuild now presents one visible guided path: choose a task, add a
video, connect a compatible model when needed, prepare the run, watch the job,
review the result, and export reviewed objects. Job state is normalized through
backend lifecycle summaries and UI selectors before rendering, so queued,
running, waiting-review, failed, canceled, and export-ready states have a single
source of truth.

SAM2 and SAM3 selections now keep provider ID, connection ID, profile ID,
display label, engine, locality, and hosted opt-in separate. The normal guided
path supports SAM2 local/hosted prompt tracking, SAM3 local/hosted concept or
exemplar workflows, and no-model motion/import paths without making users pick
raw provider internals.

## Phase Commits

| Phase | Commit | Focus |
| --- | --- | --- |
| 0 | `f13f667` | Audited the existing Local UI flow and job-state blockers. |
| 1 | `24c2536` | Added backend/UI job lifecycle summaries. |
| 2 | `de7b135` | Normalized provider selection across SAM2 and SAM3. |
| 3 | `e9048e7` | Simplified the guided flow and exposed the main Job Center. |
| 4 | `822989c` | Drove workflow screens from normalized state selectors. |
| 5 | `54eef14` | Clarified review tracking and export gates. |
| 6 | `d48ecdc` | Updated documentation, notebooks, and system requirements. |
| 7 | `test: cover guided UI lifecycle and job center states` | Covered guided UI lifecycle and job center states. |

## Acceptance Audit

- One primary flow: the visible workflow is the guided Start -> Video -> Model
  -> Prepare -> Review/export path. The old competing surfaces are hidden or
  scoped as advanced/internal views.
- One primary action per screen: layout checks now assert exactly one visible
  workflow footer primary action for guided states.
- Current job visibility: review and failure captures now assert the selected
  job is visible in the main Job Center, including status and job ID.
- Plain-language failures: failed review captures assert failed status,
  provider failure text, logs, and fallback diagnostics are surfaced.
- Provider neutrality: SAM2/SAM3 local/hosted and no-model provider fixtures
  assert normalized provider contracts and compatible connection lists.
- No fake confidence: selector tests preserve the distinction between pending
  preview estimates, debug fixtures, terminal API tracks, and fallback-only
  jobs.
- Export safety: review and export gates require reviewed exportable tracks;
  handoff cards expose compact status/action copy.
- Hosted safety: diagnostics and docs continue to report hosted provider key
  and opt-in gaps without attempting network calls.

## Validation Summary

- `python3 -m pytest`: passed, 465 passed and 1 skipped.
- `npm test`: passed, 21 Node tests.
- `npm run lint`: passed.
- `npm run build`: passed.
- `npm run embed:smoke`: passed.
- `python3 -m motionjson.cli backend diagnostics --json`: passed and reported
  SAM2/SAM3/CUDA/key gaps as optional setup diagnostics.
- `python3 -m motionjson.cli backend diagnostics --text`: passed with the same
  provider guidance in text form.
- `python3 -m motionjson.cli ui --help`: passed.
- Focused `npm run ui:layout` matrices passed across 390x844, 768x1024,
  1024x768, 1366x768, 1440x900, and 1920x1080 for the changed guided, review,
  failure, correction, and export states.

## Remaining Risks

- The exhaustive default `npm run ui:layout` command still idles silently in
  the Chrome CDP harness and was stopped after several minutes. Focused
  phase-relevant matrices complete and are the current browser evidence.
- Real SAM2/SAM3 model execution was not run. This audit used CPU/no-model,
  mock, diagnostics, and provider-contract coverage.
- Hosted providers were not called because they require explicit user-supplied
  credentials and network/cost opt-in.
- Colab notebooks were source/structure validated in Phase 6, but not executed
  end to end inside Colab.

## Follow-Up Tasks

- Add bounded timeout/progress reporting to `scripts/check_local_ui_layout.mjs`
  so the exhaustive default matrix can be trusted in CI.
- Run real local SAM2/SAM3 smoke tests in configured GPU environments.
- Run hosted-provider smoke tests only after a human supplies keys and confirms
  network/cost usage.
- Refresh committed docs screenshots after the layout harness timeout issue is
  fixed or scoped per screenshot group.
