# Phase Flow Rebuild 2 Report

## Summary

- Added a normalized Local UI model connection contract that keeps connection ID,
  provider ID, engine, display label, hosted profile, locality, capabilities,
  readiness, and hosted-call opt-in as separate fields.
- Updated guided SAM2/SAM3 routing so normal text-prompt workflows prefer SAM3
  concept discovery, single-object SAM3 routes through exemplar mode, SAM2 stays
  on manual prompt tracing, and detector fallback remains advanced/mock-only.
- Updated run-plan and workflow summary logic to use provider IDs for policy and
  display labels for user-facing names.
- Kept no-model workflows on clean `motion`, `external`, `threshold`, and `mock`
  paths without requiring model setup.
- Documented the provider-neutral connection contract in `docs/local_ui.md`.

## Changed Files

- `src/motionjson/ui/static/app.js`
- `scripts/test_ui_config_builder.mjs`
- `docs/local_ui.md`
- `docs/roadmap/phase-flow-rebuild-2-report.md`

## Tests Run

- `npm test`
- `npm run build`
- `python3 -m pytest -q tests/test_provider_settings.py tests/test_sam2_providers.py tests/test_sam3_providers.py tests/test_config.py`

The JS config-builder test now validates SAM2 local, SAM2 hosted, SAM3 local
single-object, SAM3 local auto-mask, SAM3 hosted, hosted opt-in negative,
motion, and external generated configs through Python
`ExtractionRunConfig.from_dict`.

## Browser Evidence

No new screenshot set was captured for this phase because the changes are
provider-contract and run-config logic only. The existing Model Connections
panel markup is preserved, with display labels/status strings updated through
the same card structure. Phase 3 is the planned visible workflow/layout rebuild
and will capture required before/after browser evidence.

## Known Limitations

- Provider readiness still depends on the existing provider settings and
  capability payloads; this phase normalizes UI selection logic but does not add
  new backend capability probes.
- Legacy detector workflows remain available only through explicit advanced or
  debug/mock paths.
- The pre-existing untracked rebuild prompt file was left unstaged.

## Follow-Up Tasks

- Phase 3 should remove competing visible flow models and make the Job Center a
  main-flow state.
- Phase 4 should move remaining frontend gate/action derivation into pure
  selectors backed by the Phase 1 lifecycle contract.
