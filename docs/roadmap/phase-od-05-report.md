---
historical: true
default_context: false
---

# Phase OD-05 Report - API-Rendered Object Discovery Browser

## Summary

Phase OD-05 makes the Local UI's discovery path API-first. The default goal is
now Discover objects, which builds `auto_object_proposals` run configs with
Clean, Balanced, or Maximum Recall presets. Trace Everything is available only
behind an advanced acknowledgement control. The review rail renders
`review.candidates` from the backend, supports candidate selection and filters,
shows artifact-backed thumbnail/mask previews, and calls
`POST /api/jobs/{jobId}/track-selected` to track selected candidates.

Normal terminal jobs without API tracks no longer synthesize final track rows.
Synthetic preview tracks remain only as non-exportable `demoMode` in-flight
estimates while a job is still pending/running.

## Changed Files

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/backend/corrections.py`
- `scripts/test_ui_config_builder.mjs`
- `tests/test_phase11a_text_guided_discovery.py`
- `docs/local_ui.md`
- `docs/discovery_providers.md`
- `docs/roadmap/phase-od-05-report.md`

## Tests Run

- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- `python3 -m pytest tests/test_backend_track_corrections.py::test_local_track_edit_export_inclusion_does_not_hide_track tests/test_local_ui_api.py::test_local_ui_track_selected_validates_candidates_and_gates_export tests/test_phase11a_text_guided_discovery.py::test_phase11a_static_ui_surfaces_candidate_summary_review -q`
- `python3 -m pytest -q`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- Browser smoke: launched `python3 -m motionjson.cli ui --no-open --mock --host 127.0.0.1 --port 8765`, opened the Local UI in the in-app browser, verified Discover objects as the active goal, ran a mock object-discovery job, verified API candidate rows and selected-candidate checkboxes, clicked Track selected, confirmed four API tracks stayed `review_pending`, and checked no horizontal overflow.
- Rendering scout: reviewed the UI diff for candidate API boundaries, selected tracking UX, synthetic-track isolation, and responsive risk. Follow-up fixes made `review.candidates` the only selectable candidate source, added selected-tracking payload tests, wrapped candidate card headers, and corrected the first-paint preset label.
- `git diff --check`

## Known Limitations

- Track approval still uses the existing correction/export controls; there is
  not yet a dedicated one-click approval action for `review_pending` selected
  tracks.
- Candidate thumbnails depend on artifact registration. If a provider writes no
  preview artifacts, the browser falls back to frame/geometry text.
- The UI still exposes older discovery goals for compatibility, but the
  discovery-first path is now the default.

## Follow-Up Tasks

- OD-06 should wire SAM2 automatic proposals into the same API candidate shape.
- OD-10 should expand the Trace Everything expert workflow and copy once backend
  caps and warnings are complete.
