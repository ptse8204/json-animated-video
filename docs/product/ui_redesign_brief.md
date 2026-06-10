# UI Redesign Brief

The Local UI may abandon cards, right rails, steppers, dashboards, panel layout, and current visual hierarchy.

Do not read old UI audits, design-system notes, roadmap reports, or archived prompt packets for redesign work unless the user explicitly asks for history.

Use source and tests for implementation truth:

- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/`
- `scripts/check_local_ui_layout.mjs`
- UI tests listed in `docs/codex/CONTEXT_MANIFEST.yaml`

Required product behavior:

- source identity: user knows the project/video/source;
- goal clarity: user knows what will be traced;
- provider readiness: user knows whether the chosen provider/model can run;
- consent: hosted/network/cost/privacy boundaries need explicit acknowledgement;
- run progress: queued/running/blocked/failed/complete states are clear;
- failure recovery: failures explain cause and next action;
- review truth: candidates/tracks show confidence, coverage, source, warnings, corrections, and export state;
- export readiness: reviewed/selected/valid objects are clear for each export;
- rights visibility: source/generated rights warnings appear before handoff.

Safety invariants still apply. Raw JSON can remain available, but it must not dominate the nontechnical flow.
