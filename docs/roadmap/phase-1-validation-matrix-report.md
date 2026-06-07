# Phase 1 Report - Local UI Workflow Validation Matrix

## Summary

Added a versioned, machine-readable Local UI workflow matrix and regression
harness that connects visible UI workflow choices to generated run-config
fields, backend validation, provider blockers, model-planner behavior,
mock/no-model job execution, review surfaces, import review, and MotionJSON
export validation. The matrix includes 20 active cases, including mock/no-model,
threshold, motion, SAM automatic masks, external masks, SAM2/SAM3 unavailable
and mocked-ready states, hosted opt-in blockers, model planners, and review
import.

The working tree was not clean at phase start because `.gitignore` already had
an unstaged local change ignoring `codex_prompt_pack/`. That change was left
unstaged and is not part of this phase.

## Changed Files

- `tests/fixtures/local_ui_workflow_matrix.v0.1.json`
- `tests/workflow_matrix.py`
- `tests/test_local_ui_workflow_matrix.py`
- `scripts/test_ui_workflow_matrix.mjs`
- `package.json`
- `src/motionjson/ui/static/config_builder.js`
- `docs/roadmap/phase-1-validation-matrix-report.md`

## Tests Run

- `python3 -m pytest tests/test_local_ui_workflow_matrix.py` - passed, 22 tests.
- `node --test scripts/test_ui_workflow_matrix.mjs` - passed.
- `npm test` - passed, includes the new matrix JS check.
- `npm run build` - passed.
- `npm run lint` - passed.
- `python3 -m pytest tests/test_local_ui_api.py tests/test_model_connectors.py tests/test_local_ui_workflow_matrix.py` - passed, 74 tests.
- `npm run ui:layout -- --state workflow-provider --viewport laptop-1366` - passed.
- `npm run ui:layout -- --state diagnostics-open --viewport mobile-390` - passed.
- `npm run ui:layout -- --state workflow-keyboard --viewport mobile-390` - passed.
- `npm run ui:layout` - did not produce a stable full-suite result in this environment: repeated full runs timed out or hung on changing capture-readiness states, while those same states passed individually. No layout files were changed in this phase.
- `git diff --check` - passed.

## Known Limitations

- Backend `/api/run-config/validate` reports unavailable optional providers as
  structured error-severity warnings unless config shape is invalid or the
  local SAM3 concept/exemplar blocker applies. The matrix records this actual
  contract instead of treating all blocked UI paths as backend `valid: false`.
- The matrix uses controlled capability reports for optional SAM2/SAM3/hosted
  readiness, so default tests do not require GPU, model weights, credentials,
  or hosted network calls.
- The full default layout matrix remains timing-sensitive on this machine; the
  phase verified targeted layout states but did not gate on the full command.
- A read-only diff-review scout initially found missing `sam_auto_masks`
  coverage and a backend/UI builder drift risk. Both were addressed before
  commit by adding SAM automatic-mask matrix cases and feeding JS
  `buildRunConfig` output into the backend validation tests.

## Follow-Up Tasks

- Phase 2 should replace duplicated provider/workflow definitions with one
  provider registry and add drift tests against this matrix.
- Phase 4 should promote the matrix cases into browser E2E journeys with stable
  selectors and deterministic mock/no-model setup.
- A future layout-harness hardening pass should make the full `npm run
  ui:layout` command stable across all default viewports and capture states.
