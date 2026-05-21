# Phase UI-MODEL-07 Report - Guided Review And Correction UX

## Summary

UI-MODEL-07 makes the post-extraction review path clearer for nontechnical
users. Candidate cards now keep stable thumbnail/mask preview slots, show
explicit review status chips, and provide retry guidance when candidates look
too broad, weak, hidden by filters, or missing. The correction panel now starts
with selected-track guidance before edit controls. The export panel states and
summarizes the reviewed-selected-only gate before validation details.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/roadmap/phase-ui-model-07-report.md`
- `docs/design/screenshots/ui-model-07-before/`
- `docs/design/screenshots/ui-model-07/`
- `docs/design/screenshots/ui-model-07-docs/`

## Browser Evidence

Before:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-07-before
```

After:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-07
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-07-docs
```

Required viewports covered: 390x844, 768x1024, 1024x768, 1366x768,
1440x900, and 1920x1080.

New UI states covered: `candidate-review`, `correction-tools`, and
`export-gate`.

Visual findings:

- Before screenshots showed the seeded job review path, but correction tools
  were not isolated and the candidate card hierarchy only exposed the simple
  selected/pending path.
- After screenshots show candidate cards with stable thumbnail/mask slots,
  selected/rejected/background-like/duplicate/low-confidence/needs-review/
  reviewed-for-export chips, and retry guidance.
- Correction screenshots show selected-track export state, prompt readiness,
  merge readiness, edit controls, merge suggestions, and correction history in
  one readable state.
- Export screenshots show the reviewed-selected-only gate before lower-level
  validation, rights, and artifact details.
- Rendering review found the export CTA still looked active after failed
  validation. The final screenshots now show a disabled `Resolve validation
  first` action when validation has blocking issues.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_local_ui_api.py -k "review or export"`
- `python3 -m pytest -q tests -k "review or export or ui"`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-07`
- `python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-07-docs`
- `python3 -m pytest -q tests/test_docs_links.py`
- `git diff --check`

## Known Limitations

- Screenshot fixtures use deterministic review data for candidate status
  variety; real previews still depend on workers registering thumbnail and mask
  preview artifacts.
- Retry suggestions are local UI guidance only. They do not automatically
  modify the next run config yet.
- The export handoff remains the existing MotionJSON export action; one-click
  export package cards are planned for UI-MODEL-08.

## Follow-Up Tasks

- UI-MODEL-08 should convert the reviewed export state into one-click Website,
  MotionJSON, runtime snippet, Remotion, and developer handoff cards.
- A later backend slice can add richer candidate preview generation for
  provider paths that do not currently register thumbnails.
