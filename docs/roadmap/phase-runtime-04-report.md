---
historical: true
default_context: false
---

# Phase runtime-04: Truthful adaptive effort reporting

## Summary

This phase makes guided effort tuning visible in run configs and debug reports.
The UI could already auto-reduce sample FPS, max frames, max objects, or quality
after asset-prep failures, but debug reports only showed the resolved numeric
values next to the original effort label. That made a run look contradictory,
for example `effortPreset: high_quality` with `sampleFps: 6`.

Run configs now carry a sanitized `discovery.config.adaptiveParameters` block
when the UI applies adaptive defaults. Debug reports include that block so users
can see the prior failure reason, resolved values, auto/user-override sources,
materialization risk, and chip explanations.

No layout surfaces were changed in this phase, so browser screenshot evidence
was not required.

## Changed files

- `src/motionjson/ui/static/app.js`
  - Adds sanitized adaptive-parameter config metadata in object-discovery and
    SAM3 scene-sweep config paths.
  - Includes adaptive parameters in run debug report summaries.
  - Formats structured debug report values as JSON instead of `[object Object]`.
- `src/motionjson/ui/static/config_builder.js`
  - Adds the same sanitized adaptive-parameter block to static config builder
    outputs.
- `scripts/test_ui_config_builder.mjs`
  - Adds coverage that adaptive retry configs preserve the failure reason and
    downgrade detail.
  - Adds debug-report coverage for adaptive parameters and secret redaction.
- `docs/local_ui.md`
  - Documents `discovery.config.adaptiveParameters`.
- `docs/roadmap/phase-runtime-04-report.md`
  - Records this phase.

## Tests run

- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_local_ui_api.py tests/test_job_lifecycle.py`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `git diff --check`

## Known limitations

- This phase exposes adaptive decisions; it does not change the tuning policy.
- The config builder still has legacy mixed `preset` and `presetId` call sites.
  This phase preserves behavior and uses both in the new direct unit fixture.
- Backend workers treat adaptive metadata as diagnostic configuration; they do
  not enforce it as a separate schema yet.

## Follow-up tasks

- Normalize `preset`/`presetId` inputs in the static UI builder.
- Surface adaptive downgrade explanations directly in Run monitor, not only in
  chips and copied debug reports.
- Continue moving expensive candidate materialization behind user acceptance.
