---
historical: true
default_context: false
---

# Phase Flow Rebuild 7 Report: Guided Lifecycle And Job Center Coverage

## Summary

Added regression coverage for the rebuilt Local UI flow. The JS selector tests
now include fixture matrices for provider states and job lifecycle states, the
backend lifecycle tests cover provider identity/locality and canceled jobs, and
the layout harness asserts the key product guarantees: compact first task
choice, one visible guided primary action, visible current job details in the
main Job Center, failed job messaging, and collapsed export artifacts until
requested.

The browser capture fixture routing now seeds `workflow-correct` and
`workflow-export` with the same deterministic review fixture as the review
captures. This makes the correction/export layout assertions inspect a real
review state instead of incidental seeded backend data.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_config_builder.mjs`
- `scripts/check_local_ui_layout.mjs`
- `tests/test_job_lifecycle.py`
- `docs/roadmap/flow-rebuild-final-audit.md`
- `docs/roadmap/phase-flow-rebuild-7-report.md`

## Tests Run

- `python3 -m pytest`
  - Passed: 465 passed, 1 skipped.
- `python3 -m pytest -q tests/test_job_lifecycle.py`
  - Passed: 9 tests.
- `npm test`
  - Passed: 21 Node tests.
- `npm run lint`
  - Passed.
- `npm run build`
  - Passed.
- `npm run embed:smoke`
  - Passed.
- `python3 -m motionjson.cli backend diagnostics --json`
  - Passed. Reported CUDA unavailable, optional SAM2/SAM3 packages missing,
    hosted keys missing, and no-model providers ready.
- `python3 -m motionjson.cli backend diagnostics --text`
  - Passed with the same setup guidance in text form.
- `python3 -m motionjson.cli ui --help`
  - Passed.
- `npm run ui:layout -- --state workflow-goal,workflow-review,workflow-review-failure,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
  - Passed.
- `npm run ui:layout -- --state workflow-video,workflow-provider,workflow-prompts,workflow-run,prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all,workflow-correct,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
  - Failed only on a stale `workflow-export` assertion that expected a
    secondary package CTA in the simplified one-primary-action flow.
- `npm run ui:layout -- --state workflow-correct,workflow-export --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
  - Passed after updating the fixture routing and export assertion.
- `npm run ui:layout`
  - Started and then stayed silent in the Chrome/CDP harness for several
    minutes; stopped with Ctrl-C and documented as a known exhaustive-harness
    limitation.

## Browser Evidence

No docs screenshots were regenerated or committed in this phase because the
production UI layout was not visually redesigned. Browser evidence came from
the deterministic Local UI layout harness in mock/no-model mode across:

- 390x844
- 768x1024
- 1024x768
- 1366x768
- 1440x900
- 1920x1080

The passing matrices covered the changed assertions for the first task screen,
review, failed review, export handoff, correction, and export screens. The
layout harness emitted Python resource-tracker warnings about leaked semaphore
cleanup after mock job runs; the commands still returned the expected pass/fail
status.

## Known Limitations

- The full default layout matrix still needs a bounded timeout or progress
  logging fix before it can be treated as reliable CI evidence.
- Real SAM2/SAM3 model execution was not performed in this phase; coverage is
  via diagnostics, provider contracts, and mock/no-model UI smoke paths.
- Hosted providers were not called because no human-supplied credentials or
  hosted network/cost opt-in were provided.
- The UI selector currently treats absent optional action flags as false in
  tests; this matches current selector behavior but could be made more explicit
  in a future selector cleanup.

## Follow-Up Tasks

- Add a timeout/progress heartbeat to `scripts/check_local_ui_layout.mjs`.
- Consider normalizing optional UI action booleans to explicit false values.
- Run real SAM2/SAM3 and hosted-provider smoke tests in configured environments
  with explicit user approval.
