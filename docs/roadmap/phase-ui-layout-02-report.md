# Phase UI-LAYOUT-02 Report - Studio Review Redesign

## Summary

UI-LAYOUT-02 redesigned the Local UI result/review surface to follow the
provided studio mockup: a minimal top workflow bar, a large video preview with
object overlays, a first-class "Review all objects" panel, and a full-width
website package export call to action.

The phase also adds a `Trace all objects` goal across the UI and config
builders, routes fake model planning for that goal through
`auto_object_proposals`, and keeps SAM2/SAM3 setup visible through the existing
model connection flow. Hosted/provider failures remain surfaced in diagnostics;
normal review states keep the details rail collapsed until requested.

The working tree was clean at phase start.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/config.py`
- `src/motionjson/model_connectors/contracts.py`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_model_connectors.py`
- `tests/test_phase8_ui_config_builder.py`
- `docs/design/screenshots/phase-ui-studio-redesign/*`
- `docs/roadmap/phase-ui-layout-02-report.md`

## Browser Evidence

Before screenshots were captured from a detached HEAD worktree into:

```bash
docs/design/screenshots/phase-ui-studio-redesign/before
```

The before layout command produced screenshots but failed the existing gate on
clipped `Mark keyframe` controls in `workflow-review`.

After screenshots were captured into:

```bash
docs/design/screenshots/phase-ui-studio-redesign/after
```

After layout validation passed for:

- 390x844
- 768x1024
- 1024x768
- 1366x768
- 1440x900
- 1920x1080

States covered:

- `workflow-review`
- `candidate-review`
- `export-handoff`
- `workflow-review-failure` at 390x844 and 1440x900

Representative after screenshot:

```text
docs/design/screenshots/phase-ui-studio-redesign/after/desktop-1440-workflow-review.png
```

## Implementation Notes

- Replaced the visible shell with a simplified MotionJSON header and 5-step
  progress bar: Video, Model, Prompt, Run, Result.
- Added the visible `Trace all objects` goal and preserved the existing
  `auto_object_proposals` path for clean object discovery.
- Added a compact studio review panel with object rows, confidence, frame
  counts, visibility toggles, export inclusion, background rejection, duplicate
  merge entry point, and export-selected validation.
- Added a full-width `Create website package` CTA for reviewed object exports.
- Kept advanced diagnostics available through the details rail, while collapsed
  by default for normal successful review states.
- Left failure diagnostics auto-visible when provider/fallback errors need
  immediate attention.
- Tightened config validation so `sam2-local`/`sam2-hosted` manual runs still
  require a point or box prompt unless a non-manual discovery mode is selected.

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
python3 -m pytest
```

Passed: 451 passed, 1 skipped.

```bash
python3 -m motionjson.cli --help
python3 -m motionjson.cli extract --help
python3 -m motionjson.cli backend --help
```

Passed.

```bash
node scripts/check_local_ui_layout.mjs --state workflow-review,candidate-review,export-handoff --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/phase-ui-studio-redesign/after
```

Passed. The command still emits the existing Python multiprocessing
`resource_tracker` semaphore warning during mock backend shutdown.

```bash
node scripts/check_local_ui_layout.mjs --state workflow-review-failure --viewport mobile-390,desktop-1440 --screenshot-dir docs/design/screenshots/phase-ui-studio-redesign/after
```

Passed.

```bash
git diff --check
```

Passed.

## Known Limitations

- The screenshot fixture uses a CSS-generated demo frame for the browser
  evidence instead of embedding a real video asset; real uploaded/registered
  videos still render through the existing `<video>` preview path.
- The studio overlay currently draws boxes and translucent regions from track
  geometry. True mask image compositing depends on available backend mask
  artifacts.
- The hidden 9-step workflow remains in the DOM for keyboard/test compatibility
  while the visible UI presents the simplified 5-step model.
- The design follows the reference mockup closely, but the exact photographic
  garden frame is not bundled as a committed asset.

## Follow-Up Tasks

- Add real preview-mask artifact compositing when mask image artifacts are
  available from jobs.
- Add a compact top-left frame/time badge and a 1080p badge inside the viewer.
- Connect `Create website package` to a dedicated website-package action once
  export routes expose that as an explicit first-class endpoint.
- Consider adding a proper design token layer for the studio shell instead of
  relying on a final CSS override block.
