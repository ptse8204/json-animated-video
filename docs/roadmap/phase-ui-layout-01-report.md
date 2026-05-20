# Phase UI-LAYOUT-01 Report - Local UI Readability

## Summary

UI-LAYOUT-01 used browser-rendered evidence to improve the Local UI shell's
readability and responsive behavior. The phase focused on reducing default
panel density, keeping diagnostics secondary until requested, making capture
states responsive, widening cramped tablet/desktop sidebar panels, and
strengthening the headless Chrome layout gate.

The working tree was clean at phase start after UI-MODEL-00 was committed.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `scripts/check_local_ui_layout.mjs`
- `docs/design/local-ui-audit.md`
- `docs/roadmap/phase-ui-layout-01-report.md`
- `docs/design/screenshots/ui-layout-01-before/*`
- `docs/design/screenshots/ui-layout-01/*`
- `docs/design/screenshots/ui-layout-01-docs/*`

## Browser Evidence

The in-app browser was opened against the mock/no-model UI at
`http://127.0.0.1:8766/`. Browser screenshot capture timed out in the in-app
browser, so the phase used the repository headless Chrome tooling for saved
evidence.

Before screenshots:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-layout-01-before
```

After screenshots:

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-layout-01
```

Docs asset screenshots:

```bash
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-layout-01-docs
```

Viewport matrix covered:

- 390x844 mobile-like width
- 768x1024 tablet portrait
- 1024x768 tablet-like width
- 1366x768 laptop
- 1440x900 desktop
- 1920x1080 desktop

UI states covered:

- `real-empty-shell`
- `real-seeded-shell`
- `real-expanded-shell`
- `first-run`
- `new-project`
- `extraction-wizard`
- `provider-diagnostics`
- `provider-settings`
- `job-review`

## Before/After Findings

Baseline issues found by screenshots and the stricter layout gate:

- 390px states had horizontal overflow from topbar spacing.
- The `new-project` capture forced a desktop two-column shell on mobile.
- The `job-review` capture forced a two-column right rail on mobile.
- Default left rail showed workspace details, first-run diagnostics, and local
  API details too early.
- Provider settings dominated the default right rail.
- Expanded disclosure stress states squeezed diagnostic rows into narrow
  columns.

Fixes made:

- Added 390x844 and 768x1024 viewports to `scripts/check_local_ui_layout.mjs`.
- Added checks for clipped controls and too-narrow main/inspector cards.
- Collapsed secondary left-rail details by default.
- Collapsed Provider settings by default while keeping Run monitor visible.
- Made `new-project` and `job-review` capture modes responsive.
- Opened Run monitor, Review, and Artifacts/exports in the job-review capture.
- Widened the desktop/tablet sidebar and narrowed the right rail slightly.
- Fixed 390px topbar overflow.
- Documented the evidence and known compromise in `docs/design/local-ui-audit.md`.

## Tests Run

```bash
npm run build
```

Passed.

```bash
npm test
```

Passed: 21 Node tests.

```bash
npm run lint
```

Passed.

```bash
npm run ui:layout -- --check
```

Passed: Chrome available, 6 viewports, 9 states.

```bash
npm run ui:layout -- --screenshot-dir docs/design/screenshots/ui-layout-01
```

Passed across all required viewports and states. The command emits the existing
Python `resource_tracker` semaphore warning during mock job shutdown, but exits
successfully.

```bash
python3 scripts/capture_docs_assets.py --out-dir docs/design/screenshots/ui-layout-01-docs
```

Passed and generated six PNG docs assets plus `red-ball-demo.gif`.

```bash
python3 -m motionjson.cli ui --help
```

Passed.

```bash
git diff --check
```

Passed.

## Scout Review

A read-only `rendering-scout` reviewed the final diff and screenshot evidence.
It found no blocking visual regression. The scout confirmed the after matrix
supports the main layout acceptance criteria: no obvious horizontal overflow,
panel overlap, clipped primary button text, or unreadably narrow card columns
in the reviewed mobile, tablet, laptop, and desktop captures.

The scout noted that review/export remains dense. This is accepted for this
phase because UI-MODEL-07 and UI-MODEL-08 cover deeper review and export
workflow redesign.

## Known Limitations

- The UI remains dependency-free static HTML/CSS/JavaScript.
- The in-app browser opened the local UI, but its screenshot command timed out;
  saved screenshots came from the repository headless Chrome tooling.
- The right rail is still dense when review, export, and correction surfaces are
  expanded together.
- `local-ui-provider-diagnostics.png` in the docs asset set is useful layout
  evidence but does not foreground every diagnostics detail without scrolling.

## Follow-Up Tasks

- UI-MODEL-01 should replace the remaining shell-first experience with a true
  guided first-run wizard.
- UI-MODEL-07 should revisit candidate/review cards as first-class review
  surfaces instead of dense right-rail controls.
- UI-MODEL-08 should simplify export handoff into one-click export cards.
