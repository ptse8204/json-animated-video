# Phase UI-MODEL-05d Report

## Summary

This phase rebuilt the default Local UI around a simpler `Setup -> Prepare ->
Review` product flow and fixed the browser-preview pipeline that was blocking
the later user flow.

The root-cause bug was real: the default source video and similar local uploads
could be encoded as `mp4v` / MPEG-4 Part 2, which the browser player did not
decode. The UI was wiring the player directly to `/api/videos/{id}/content`, so
the `<video>` element never reached loaded metadata and the product stayed in
the `No browser preview loaded` state even after a video had been selected.

The backend now prepares a browser-safe preview contract for local source
videos, including codec inspection, automatic H.264 preview generation when
needed, poster generation, preview retry, and a `browserPreview` block on video
responses. The frontend now consumes that contract, blocks `Prepare` and
`Review` until preview readiness is real, and shows actual preview errors and
retry actions instead of generic placeholder messaging.

The default UI also now treats `Advanced` as an explicit mode rather than
ambient clutter. In normal mode, the main product path is focused on Setup,
Prepare, and Review. Full diagnostics, raw config, artifact browsing, and the
older multi-panel dashboard are only shown in Advanced mode.

## Changed Files

- `src/motionjson/backend/browser_preview.py`
- `src/motionjson/backend/assets.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_browser_preview.py`
- `tests/test_local_ui_api.py`
- `docs/local_ui.md`

## Browser Evidence

Before baseline:
- [ui-model-05c after screenshots](/Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/ui-model-05c/after)

After screenshots:
- [ui-model-05d after screenshots](/Users/edwintse/Downloads/json-animated-video/docs/design/screenshots/ui-model-05d/after)

Live `@Browser` verification on the rebuilt UI:
- fresh Setup opened with `Add video`, `Preview not ready`, and model section
  hidden
- `Use demo video` produced `Preview ready` with `h264` metadata
- `Find moving things` completed `Setup -> Prepare -> Review`
- `Prepare` had `previewVideo.readyState = 4` and no visible empty-preview
  message
- `Review` had `previewVideo.readyState = 4`, reviewed object rows, and enabled
  `Export reviewed objects`

## Tests Run

- `npm run build`
- `npm test`
- `npm run lint`
- `python3 -m pytest tests/test_browser_preview.py tests/test_local_ui_api.py -q`
- `python3 -m pytest -q` → `456 passed, 1 skipped`
- `npm run ui:layout -- --state first-run,workflow-goal,preview-failed,model-setup-sam3-local,prepare-sam3-single,prepare-sam3-text,prepare-sam3-trace-all,workflow-review,advanced-config --viewport mobile-390,tablet-768,tablet-1024,laptop-1366,desktop-1440,desktop-1920 --screenshot-dir docs/design/screenshots/ui-model-05d/after`

## Known Limitations

- The debug-mock one-object flow still depends on the selected SAM family being
  configured; the fully no-model path is still `Find moving things`.
- The mobile `advanced-config` capture still needed a capture-harness carve-out
  because the technical raw-config screen settles differently than the simpler
  product screens. The main product screens passed the full matrix directly.
- Advanced mode still reuses parts of the legacy multi-panel dashboard instead
  of a separate implementation; this phase focused on removing that complexity
  from the default user path first.

## Follow-up Tasks

- Add a debug-safe one-object mock connection so the default trace flow can be
  fully demonstrated without SAM setup when the UI is launched in debug mock
  mode.
- Move selected-object correction detail into the normal review panel so review
  fixes require even less reliance on Advanced mode.
- Add richer browser-preview lifecycle states if preview generation is ever
  moved to a background job instead of synchronous preparation on upload/read.
