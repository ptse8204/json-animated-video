# Phase UI Review Export UX 01 Report

## Summary

This phase improves the last Review and Export step after the export state fix
from the previous phase.

Current UX evaluation before the change:

- The UI could show reviewed moving tracks while the export step still looked
  blocked.
- The final action often became a disabled `Resolve validation first` button,
  which explained the state but did not give the user a concrete recovery path.
- Validation failures were summarized as generic export validation copy in the
  main flow, while the exact backend issue lived deeper in the export details.
- On mobile, the sticky guided footer could be the only visible final-step
  control, so the primary label needed to be actionable and high contrast.

Implementation:

- Added a plain-language export readiness band in the review panel and export
  rail. It states what will export, whether validation is needed, the first
  blocking issue when present, and the next action.
- Changed validation-blocked guided footer behavior from a disabled export
  dead end to an enabled `Validate again` action when revalidation is the next
  useful step.
- Surfaced the first backend export validation issue in post-run flow cards,
  export gate rows, readiness checklist rows, and action tooltips.
- Improved disabled guided-primary button contrast for states that remain truly
  blocked.

## Changed Files

- `src/motionjson/ui/static/app.js`
  - Added `exportValidationIssueText`, `exportDecisionState`, and
    `exportDecisionMarkup`.
  - Routed validation-blocked guided primary action to `validateSelectedExport`.
  - Passed exact validation issue copy through workflow and post-run snapshots.
- `src/motionjson/ui/static/app.css`
  - Added compact export readiness band styles and responsive behavior.
  - Improved disabled guided-primary button contrast.
- `src/motionjson/ui/static/index.html`
  - Added export decision slots to the review card and export rail.
- `scripts/test_ui_config_builder.mjs`
  - Added regression coverage for exact validation issue copy, blocked export
    decision state, ready export decision state, and post-run validation copy.
- `docs/design/screenshots/ui-review-export-ux-01/`
  - Added before/after browser evidence for `workflow-review`,
    `workflow-export`, `export-gate`, `export-handoff`, and `export-success`
    at 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and 1920x1080.

## Browser Evidence

Before evidence showed the mobile export gate with a disabled `Resolve
validation first` primary action and generic validation text. After evidence
shows the same state with:

- concrete validation issue text in the post-run flow;
- an enabled `Validate again` primary action;
- an export readiness band in the review/export panel;
- success state copy that says reviewed objects are ready to export.

The local Chrome smoke verified:

- `export-gate`: primary action `Validate again`, not disabled; exact validation
  issue visible; no horizontal overflow.
- `export-success`: decision text `Ready to export 4 reviewed objects`; handoff
  buttons available for ZIP, scene, snippet, Remotion plan, and bundle; no
  horizontal overflow.

## Tests Run

- `npm test`
- `npm run build`
- `npm run lint`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-review-export-ux-01/before --state workflow-review,workflow-export,export-gate,export-handoff,export-success --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-review-export-ux-01/after --state workflow-review,workflow-export,export-gate,export-handoff,export-success --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q tests/test_local_ui_api.py::test_local_ui_exports_accepted_track_summary_with_masks_when_scene_review_gate_is_stale tests/test_final_export.py::test_export_ready_track_summary_overrides_stale_scene_review_gate`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli extract --help`
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m motionjson.cli backend --help`
- `git diff --check`

## Known Limitations

- The live Colab tab still needs the latest local commit deployed or restarted
  before it receives these UI changes.
- The readiness band does not replace the detailed export diagnostics; it
  summarizes the first actionable issue and keeps deeper technical rows in the
  export rail.
- Existing mobile sticky-footer behavior is preserved. This phase improves the
  CTA label and issue copy rather than redesigning the footer placement.

## Follow-Up Tasks

- Add a small inline link or focus target from the readiness band to the exact
  export diagnostics row when the export rail is open.
- Consider moving the export readiness band above the object list on very small
  viewports so the blocking issue stays visible without relying on the post-run
  flow card.
- Add an end-to-end UI test that clicks the guided `Validate again` footer
  button and asserts that the validation request runs.
