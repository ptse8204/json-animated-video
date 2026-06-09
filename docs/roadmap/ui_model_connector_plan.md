# UI Model Connector Roadmap

This is the active Codex roadmap for turning MotionJSON's local UI into a
nontechnical, guided object-tracing workflow with a safe server-side model
planning connector. It builds on, and does not erase, the completed Phase 0-14
and OD phase history under `docs/roadmap/`.

## Baseline

The baseline for this roadmap is the repository status after OD-14, recorded in
`docs/repo_status.md` and the OD phase reports. At that point MotionJSON already
has a dependency-light static Local UI, mock/no-model extraction paths,
provider diagnostics, provider settings with redaction, API-first candidate
review payloads, selected-candidate tracking, review-gated exports, and
headless Chrome layout validation for several desktop/tablet viewports.

This roadmap does not restart the original product roadmap. It continues from
that baseline and focuses on guided nontechnical workflows, browser-verified UI
readability, safe model-assisted planning, review/correction clarity, and export
handoff.

## Operating Rules

- Work phase by phase in the order listed here.
- End every completed phase with a git commit and a phase report.
- The master Codex agent owns planning, implementation, validation, review
  synthesis, and commits end to end.
- Use bounded read-only scouts only when they materially reduce risk. Suitable
  scouts are `plan-risk-scout`, `diff-review-scout`, `rendering-scout`,
  `test-gap-scout`, and `adoption-scout`.
- Use at most one or two scouts per phase unless the user explicitly asks for
  more.
- Preserve CLI compatibility unless a phase explicitly migrates an interface
  with documentation and tests.
- Keep heavyweight ML dependencies optional and capability-gated.
- Preserve CPU/mock/no-model operation for tests and UI smoke checks.
- Never put model API keys in browser code.
- Never make hosted calls without explicit user opt-in.
- Preserve provider settings environment-variable precedence.
- Keep UI-saved hosted credentials settings-only until a phase explicitly wires
  them to a runtime connector with tests.
- Redact secrets from API responses, run configs, artifacts, logs, screenshots,
  validation errors, and phase reports.
- Keep raw JSON available for technical users but visually secondary to the
  nontechnical path.

## Browser Evidence Policy

Every phase that touches UI layout, cards, fonts, visual hierarchy, panels,
tool layout, right rail, wizard layout, provider settings, review cards, export
cards, or responsive behavior must use rendered browser evidence.

Required workflow:

1. Start the local UI in mock/no-model mode.
2. Open it with the Codex in-app browser when available, otherwise use the
   repository headless Chrome/layout tooling.
3. Capture before screenshots before changing layout.
4. Inspect the screenshots before coding.
5. Make the smallest coherent improvement for the phase.
6. Capture after screenshots.
7. Compare before and after evidence in the phase report.
8. Save screenshot evidence under `docs/design/screenshots/<phase-id>/` unless
   a phase report explains why the repository policy requires otherwise.

Required viewports for layout phases:

- 390x844 mobile-like narrow viewport
- 768x1024 tablet portrait
- 1024x768 tablet-like width
- 1366x768 laptop
- 1440x900 desktop
- 1920x1080 desktop

Hard layout acceptance criteria:

- no horizontal page overflow at required viewports;
- no card or panel overlap;
- no clipped primary button text;
- no unreadably narrow card columns;
- no dense control wall in the first-run/default view;
- advanced controls are visually secondary;
- primary user path is readable without understanding raw JSON;
- labels, provider names, and long status text wrap gracefully;
- forms preserve labels and input affordance at small widths;
- keyboard access remains intact.

## Phase Table

### UI-MODEL-00 - Align Codex workflow with this roadmap

Purpose: update repo-level Codex instructions so future sessions know this
roadmap, the browser evidence policy, and the master-agent workflow.

Expected commit:

```bash
git commit -m "phase ui-model-00: align codex workflow with model connector roadmap"
```

Acceptance:

- `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, `codex_tasks.yaml`, and docs links
  point to this active roadmap.
- The roadmap is self-contained and does not depend on hidden chat context.
- Existing phase history is preserved.
- No product code behavior changes.

### UI-LAYOUT-01 - Browser-driven layout and readability overhaul

Purpose: make the current local UI easier to read and use by improving card
layout, fonts, spacing, panel density, tool grouping, right-rail hierarchy,
review/export card hierarchy, and responsive behavior.

Expected commit:

```bash
git commit -m "phase ui-layout-01: improve local ui readability and card layout"
```

Acceptance:

- Before and after screenshots exist for required viewports and key UI states.
- Layout checks catch overflow, overlap, clipped button text, and too-narrow
  cards.
- `docs/design/local-ui-audit.md` or a linked design report records the visual
  findings and improvements.
- A rendering scout reviews screenshots and final diff before commit.

### UI-MODEL-01 - Nontechnical first-run wizard

Purpose: add a guided default path for adding a video, choosing a goal,
confirming privacy/model mode, validating a plan, running extraction, reviewing
candidates, and exporting without CLI knowledge.

Expected commit:

```bash
git commit -m "phase ui-model-01: add guided first-run wizard"
```

Acceptance:

- Goal cards cover Cut out one object, Find moving things, Find by
  description, Import masks, and Review previous result.
- Local path registration remains available under Advanced.
- A human-readable run plan replaces default raw JSON emphasis.
- Raw config preview remains available behind advanced disclosure.
- Empty, error, loading, and success states are clear.

### UI-MODEL-02 - Model connector backend contract

Purpose: create the server-side abstraction for model-assisted planning without
depending on hosted calls.

Expected commit:

```bash
git commit -m "phase ui-model-02: add model connector contract"
```

Acceptance:

- Typed connector interfaces, request/result/event models, deterministic fake
  connector, and API routes exist.
- Routes support provider listing, readiness, test, estimate, start, poll
  events, cancellation, and attaching model plans to jobs.
- Credentials remain server-side.
- Default tests make no network calls.

### UI-MODEL-03 - Provider settings to connector wiring

Purpose: connect existing provider settings to connector readiness, testing,
and estimates while preserving redaction and local/mock defaults.

Expected commit:

```bash
git commit -m "phase ui-model-03: wire provider settings to model connectors"
```

Acceptance:

- Saved settings and environment precedence feed connector readiness.
- Hosted providers require explicit hosted-call opt-in.
- No raw secrets are returned to UI responses, logs, screenshots, or tests.
- No-network hosted checks remain setup-only by default.

### UI-MODEL-04 - OpenAI planning connector MVP

Purpose: add an OpenAI planning connector for intent parsing, object labels,
suggested keyframes, run-plan generation, and troubleshooting explanations.

Expected commit:

```bash
git commit -m "phase ui-model-04: add openai planning connector"
```

Acceptance:

- The connector is server-side only and uses mocked transport in tests.
- Hosted API calls are disabled by default and require explicit opt-in plus
  valid server-side configuration.
- Model output is validated as a proposed plan, not trusted extraction truth.
- Segmentation and tracking remain routed through explicit CV providers.

### UI-MODEL-05 - UI connect-model flow

Purpose: add a nontechnical setup flow for choosing local/mock/hosted
providers, testing readiness, reviewing privacy/cost, saving redacted settings,
and confirming hosted runs.

Expected commit:

```bash
git commit -m "phase ui-model-05: add model setup wizard"
```

Acceptance:

- Local/mock options appear first.
- Hosted providers show clear privacy and cost warnings before saving.
- Test states cover success, missing config, invalid key format, and no-network
  safety.
- Raw secrets are stored only server-side and never returned to browser code.

### UI-MODEL-06 - Model plan to extraction run

Purpose: convert model-generated run plans into validated
`ExtractionRunConfig`, enqueue jobs, stream progress, and require manual
confirmation before real runs.

Expected commit:

```bash
git commit -m "phase ui-model-06: route model plans into extraction jobs"
```

Acceptance:

- Plan confirmation UI shows provider readiness, privacy/cost, runtime/resource
  notes, and validation warnings.
- Generated run configs pass existing backend validation before enqueue.
- Jobs start only after user confirmation.
- Model-plan and extraction progress appear in the existing job/event UI.

### UI-MODEL-07 - Review UX upgrade

Purpose: improve candidate review, thumbnails, statuses, suggested retries,
correction explanations, and reviewed-only export gating.

Expected commit:

```bash
git commit -m "phase ui-model-07: improve guided review and correction ux"
```

Acceptance:

- Candidate cards show thumbnail or mask preview when available.
- Review statuses include selected, rejected, background-like, duplicate, low
  confidence, needs review, and reviewed for export.
- Retry suggestions point users toward Maximum Recall, smaller max area, moving
  object workflow, additional prompts, or mask import as appropriate.
- Export defaults to reviewed selected objects only.

### UI-MODEL-08 - Seamless export handoff

Purpose: simplify export for nontechnical and developer users.

Expected commit:

```bash
git commit -m "phase ui-model-08: simplify export handoff"
```

Acceptance:

- One-click export cards exist for Website package, MotionJSON scene, Runtime
  snippet, Remotion plan, and Developer handoff.
- Rights warnings and reviewed-object status are shown in plain language.
- Advanced export toggles remain available under Advanced.
- Success states include copyable next steps.

### UI-MODEL-09 - Codex operational integration

Purpose: add Codex-ready prompts and review workflows for continuing this
project safely.

Expected commit:

```bash
git commit -m "phase ui-model-09: add codex operational prompts"
```

Acceptance:

- Prompt docs cover UI layout review, browser screenshot review, model connector
  review, release audit, and review-only scout prompts.
- AGENTS review guidelines are updated.
- Any automation is guarded and cannot push unsafe changes without review.

### UI-MODEL-10 - Release hardening

Purpose: harden the repository for public adoption and release.

Expected commit:

```bash
git commit -m "phase ui-model-10: harden release readiness"
```

Acceptance:

- License status is resolved or explicitly documented.
- Issue templates, release checklist, screenshot freshness checks, and security
  recommendations cover the model connector and UI layout work.
- README and docs match implemented features only.
- Full available CI or documented equivalent validation has run.

### UI-WORKFLOW-11 - Guided workflow rescue and inline run/review shell

Purpose: simplify the guided workspace around the real user path, move critical
review and correction surfaces back into the main screen, improve live run
visibility, and add faster first-pass selection plus automatic object naming.

Expected commit:

```bash
git commit -m "phase ui-workflow-11: streamline guided run and review workflow"
```

Acceptance:

- The first-run goal grid favors `Cut out one object`, `Pick objects from one
  frame`, `Find by description`, and `Review previous result`, while the
  noisier full-scene sweep remains available as an advanced task.
- The default run path no longer depends on the right diagnostics rail for
  candidate review, correction history, or export gating.
- Run monitor shows inline live previews of masks, cutouts, or candidate
  previews as soon as they are registered for the active job.
- Logs/events are readable in a terminal-style surface with stage, progress,
  and recovery context.
- Generic placeholder object names are replaced with local automatic labels
  when the optional lightweight classifier is available, while user labels
  remain authoritative.
- The new `Pick objects from one frame` goal uses the current frame as a fast
  first proposal pass before selected tracking.

### UI-WORKFLOW-12 - Finish fast keyframe workflow and compact editor shell

Purpose: complete the keyframe-first object-pick workflow so it no longer
behaves like scene sweep, tighten model setup around required inputs, and
finish the compact editor direction across run/review/export.

Expected commit:

```bash
git commit -m "phase ui-workflow-12: finish keyframe-first tracking workflow"
```

Acceptance:

- `Pick objects from one frame` is a real two-stage path:
  scan keyframe, inspect/select/rename objects, then track selected objects
  only in a child job.
- The scan job writes one-frame candidate artifacts only and does not
  precompute full candidate mask sequences.
- `POST /api/jobs/{jobId}/track-selected` accepts
  `trackMode: "keyframe_selected_only"` and returns a queued child tracking job.
- The compact editor shell no longer depends on the diagnostics rail for the
  normal workflow.
- Model setup shows required Hugging Face access before cache/smoke when the
  selected runtime needs it.
- Automatic naming uses no-token local public weights and records label
  provenance in review metadata.

### UI-WORKFLOW-13 - Correct inline workflow and live-output gaps

Purpose: finish the corrective UX pass after UI-WORKFLOW-12 by removing the
remaining all-panels dependency, enforcing explicit keyframe selection, making
live output visible in the normal run monitor, and tightening the export gate.

Expected commit:

```bash
git commit -m "phase ui-workflow-13: correct inline workflow gaps"
```

Acceptance:

- Advanced tracing tasks are visible inline on the Start screen by default;
  the all-panels/details workflow controls are removed from the normal shell.
- `Pick objects from one frame` cannot validate or start until the user has
  confirmed the exact scan frame.
- Candidate-scan preview artifacts are checkpointed while jobs run, and the
  run monitor shows live candidate, mask, and cutout previews in the main
  workflow surface.
- SAM3 local model setup prioritizes required Hugging Face token/access inputs
  before optional provider details.
- Review/export opens as a compact working export gate: package readiness,
  included objects, rights warnings, then handoff/review tools.
