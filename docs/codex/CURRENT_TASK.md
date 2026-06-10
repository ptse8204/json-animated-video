# Current Task

ID: `UI-V3`

Goal: redesign the MotionJSON Local UI into a workflow-first object extraction
tool for less technical users while preserving backend contracts, tests, local
safety invariants, and review/export truth.

Current phase: `UI-V3-00` repo audit and task alignment.

Likely files:

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/modules/workflow.js`
- `src/motionjson/ui/static/ui_selectors.js`
- `scripts/check_local_ui_layout.mjs`
- UI tests listed in `docs/codex/CONTEXT_MANIFEST.yaml`
- compact docs only when needed for the new workflow

Validation:

```bash
npm run build
npm test
npm run lint
npm run ui:layout
git diff --check
```

Done when:

- the old card/dashboard/right-rail hierarchy is replaced by a workflow shell;
- the journey covers Goal, Source, Target, Model, Preflight, Run, Review,
  Correct, Export, and Reuse;
- the Run step has a readable extraction cockpit with usage, health, phase
  progress, visual evidence, grouped events, and contextual diagnostics;
- provider/model readiness and hosted opt-in remain truthful and safe;
- review, correction, and export gates clearly separate completed, reviewable,
  reusable, and export-ready states;
- partial failures stay recoverable and completed objects remain visible;
- raw logs/config/JSON are available but secondary;
- safety invariants and no-hosted-call defaults remain intact.
