# Phase OD-10 Report: Trace Everything Expert Mode

## Summary

Tightened Trace Everything into an explicit, bounded, review-gated expert mode.

Trace Everything already required `costWarningAcknowledged: true`; this phase
adds hard caps for keyframes, frame interval, candidates per keyframe, and
objects so expert mode cannot become unbounded through API input. Direct Trace
Everything extraction now marks generated outputs as review-required:
`tracks.json` reports `review_pending`, scene object quality metadata carries
`reviewRequired`, and export selection excludes those objects until review
state changes them.

Trace Everything configs now also reject attempts to disable `requireReview` or
`writeRejectedCandidates`.

The UI copy now tells users that Trace Everything output is slower/noisier and
blocked from export until reviewed. Docs now spell out caps, rejected-candidate
review, and export gating.

## Changed Files

- `docs/discovery_providers.md`
- `docs/local_ui.md`
- `docs/run_config.md`
- `docs/roadmap/phase-od-10-report.md`
- `src/motionjson/backend/export_workflows.py`
- `src/motionjson/config.py`
- `src/motionjson/pipeline.py`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `tests/test_config.py`
- `tests/test_discovery_providers.py`
- `tests/test_final_export.py`

## Tests Run

- `python3 -m py_compile src/motionjson/config.py src/motionjson/pipeline.py src/motionjson/backend/export_workflows.py tests/test_config.py tests/test_discovery_providers.py tests/test_final_export.py`
- `python3 -m pytest tests/test_config.py tests/test_discovery_providers.py tests/test_final_export.py -q`
- `python3 -m pytest tests/test_config.py tests/test_discovery_providers.py tests/test_final_export.py tests/test_local_ui_api.py tests/test_backend_api_product.py tests/test_docs_links.py -q`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Risk Review

The requested adoption scout could not run because the thread limit was
reached. The master agent performed the copy and safety review in-thread,
checking that Trace Everything is labeled as expert/noisy/slower and that the
review-before-export rule appears in UI and docs.

## Known Limitations

- Trace Everything still uses the existing candidate browser and review
  mechanics; this phase does not add a separate expert review wizard.
- Review completion is still represented through existing correction/export
  inclusion state. A later phase can add a clearer "mark reviewed" action if
  users need a dedicated control.

## Follow-Up Tasks

- Add a dedicated reviewed/approved state transition for expert discovery
  outputs if current correction/export controls are not obvious enough.
- Consider surfacing the exact caps in the Local UI advanced disclosure.
