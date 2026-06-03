# Phase debug-report-ui report

## Summary

- Used the active Chrome MotionJSON Local UI tab to inspect the stalled Colab SAM3 run.
- Added a copyable, redacted debug report action for selected runs in both the main run monitor and details rail.
- Verified the new action in Chrome against the local `workflow-run-stale` UI capture.

## Live Finding

- Live job id: `62b476f7068b4ee98546ef02dfa695bc`.
- Provider: `SAM3 local`.
- Status: `running`, phase `extracting`, progress `70%`.
- Watchdog: no progress update for about 17 minutes during inspection.
- Last visible event: `contours vectorized for sam3_grid_025`.
- Artifacts: `0`; objects: `1`.

The UI evidence indicates a nonterminal worker stall after SAM3 vectorized `sam3_grid_025`. Final MotionJSON artifacts were not written, so this should be handled as a stalled extraction rather than a completed run.

## Changed Files

- `src/motionjson/ui/static/index.html`
  - Added `Copy debug report` buttons beside `Open logs` in the main run monitor and details rail.
- `src/motionjson/ui/static/app.js`
  - Added `buildRunDebugReport()` with selected-run summary, watchdog state, project/video identifiers, run-config summary, recent event summaries, and suggested next step.
  - Added token/key redaction for copied report text.
  - Added clipboard handling and a short copied state label.
- `scripts/test_ui_config_builder.mjs`
  - Added stale-run debug report coverage and token redaction assertions.
- `docs/design/screenshots/phase-debug-report-ui/local-stale-run-copy-debug-report.png`
  - Saved Chrome evidence for the copied debug-report state.

## Validation

- `npm test` passed: `21` tests.
- `npm run build` passed.
- Chrome verification:
  - Opened local debug-mock UI at `http://127.0.0.1:8877/?capture=workflow-run-stale`.
  - Switched to the Run step.
  - Confirmed `Copy debug report` appears for a stale active run.
  - Clicked it and confirmed the button changes to `Copied`.

## Known Limitations

- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/phase-debug-report-ui` failed before validation because its Chrome remote debugging endpoint did not start.
- Direct terminal `curl` to the Colab `prod.colab.dev` API returned `404`, so the live investigation used visible Chrome UI/log evidence rather than cookie/session extraction.
- The new workflow copies a local report for the user to paste manually; it does not submit telemetry or create a backend support ticket.
