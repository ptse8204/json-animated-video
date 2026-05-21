# UI-MODEL-08 Phase Report

## Summary

UI-MODEL-08 simplified the Local UI export handoff for nontechnical and
developer users. The export panel now starts with destination cards for Website
package, MotionJSON scene, Runtime snippet, Remotion plan, and Developer
handoff. Advanced preset/mask/contour/preview switches remain available inside
an Advanced export settings disclosure. Successful exports show copyable next
steps with reviewed object IDs and the runtime snippet, while the panel keeps
reviewed-only gating, rights warnings, quality routing, and raw artifacts
visible for inspection.

The backend export workflow now also writes and registers
`remotion_export_plan.json` as a `remotion_plan` artifact in validated
MotionJSON handoffs.

## Changed Files

- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_local_ui_api.py`
- `docs/local_ui.md`
- `docs/design/local-ui-audit.md`
- `docs/design/screenshots/ui-model-08-before/`
- `docs/design/screenshots/ui-model-08/`
- `docs/design/screenshots/ui-model-08-docs/`

## Browser Evidence

Before screenshots:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-08-before
```

After screenshots:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-08
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-08-docs
```

Representative after evidence:

- `docs/design/screenshots/ui-model-08/desktop-1440-export-handoff.png`
- `docs/design/screenshots/ui-model-08/mobile-390-export-success-full.png`
- `docs/design/screenshots/ui-model-08/mobile-390-copyable-snippet-full.png`

The after matrix covers 390x844, 768x1024, 1024x768, 1366x768, 1440x900, and
1920x1080. It includes the new `export-handoff`, `export-success`, and
`copyable-snippet` states, plus full-page mobile captures for the long export
handoff stack.

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest -q tests/test_local_ui_api.py -k export`
- `python3 -m pytest -q tests -k "export or embed or ui"`
- `npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-model-08`
- `python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-model-08-docs`
- `python3 -m pytest -q tests/test_docs_links.py`
- `git diff --check`

## Review Notes

A read-only rendering scout reviewed the final diff and export screenshots. Two
material findings were fixed before commit:

- the screenshot capture selector now targets only top-level right-rail
  sections so the nested Advanced export settings disclosure remains visible in
  export evidence;
- the `copyable-snippet` fixture and UI now show local copied feedback on the
  runtime snippet card, so screenshot evidence distinguishes copy-ready from
  copied state.

## Known Limitations

- The one-click cards still call the existing validated export route. They do
  not create separate per-destination backend jobs.
- Hosted/model provider behavior is unchanged in this phase.
- Copy actions use the browser clipboard API with a local textarea fallback;
  the fallback depends on browser support for `document.execCommand("copy")`.
- The docs asset capture command emits the standard docs image set. The
  export-specific evidence is captured by the layout matrix under
  `docs/design/screenshots/ui-model-08/`.

## Follow-Up Tasks

- Consider a compact artifact-browser mode for long export bundles after users
  have already chosen a handoff destination.
- Add a future end-to-end UI interaction test for clicking a handoff card,
  completing export, and copying the runtime snippet.
