---
historical: true
default_context: false
---

# Phase UI-MODEL-00 Report - Align Codex Workflow

## Summary

UI-MODEL-00 updated the repository-level Codex instructions so future sessions
can continue the guided Local UI and model connector work without hidden chat
context. The working tree was clean at phase start.

The phase adds `docs/roadmap/ui_model_connector_plan.md` as the active roadmap
for the guided UI/model connector track. It records the OD-14 baseline, phase
order, browser-rendered screenshot policy, layout acceptance criteria,
server-side model connector guardrails, report paths, validation expectations,
and expected commit messages.

The phase also updates `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, `codex_tasks.yaml`,
and `docs/index.md` so the active track is explicit and older numeric,
public-onboarding, commercial, and OD roadmaps remain preserved history unless a
user explicitly selects one.

## Changed Files

- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `codex_tasks.yaml`
- `docs/index.md`
- `docs/roadmap/ui_model_connector_plan.md`
- `docs/roadmap/phase-ui-model-00-report.md`

## Scout Review

A read-only `plan-risk-scout` reviewed the existing repo instructions and found
that old guidance still pointed future sessions at numeric Phase 0 and broad
subagent usage. The implemented updates address the material findings by:

- adding an active-roadmap pointer and precedence rule;
- namespacing the new report and phase IDs as `UI-MODEL-*` / `UI-LAYOUT-*`;
- preserving old phase reports as historical context;
- moving `codex_tasks.yaml` old phases under `historical_completed_phases`;
- adding connector guardrails for redaction, environment precedence, hosted
  opt-in, no default network calls, and server-side secrets.

## Tests Run

```bash
python3 - <<'PY'
import yaml
with open('codex_tasks.yaml', 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)
assert data['active_roadmap']['id'] == 'ui_model_connector'
assert len(data['ui_model_connector_phases']) == 12
assert data['historical_completed_phases'][0]['id'] == 0
print('codex_tasks.yaml ok')
PY
```

```bash
python3 -m motionjson.cli --help
```

```bash
npm run build
```

```bash
git diff --check
```

All commands passed.

## Screenshot Evidence

Not required for this phase. UI-MODEL-00 changed only Codex roadmap and docs
instructions, not Local UI layout or browser-visible behavior.

## Known Limitations

- No product code or UI behavior changed in this phase.
- Documentation link checking is not exposed as a dedicated repository command;
  the phase used YAML parsing, CLI help, the existing static UI build check, and
  `git diff --check`.

## Follow-Up Tasks

- UI-LAYOUT-01 must capture browser-rendered before screenshots before making
  layout changes.
- UI-LAYOUT-01 should update design documentation with before/after visual
  findings and validate the required responsive viewports.
