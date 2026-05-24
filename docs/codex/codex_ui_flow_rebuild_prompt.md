# Goal

Rebuild the MotionJSON Local UI and job orchestration flow so a nontechnical user always knows:

1. where they are in the workflow,
2. what is required next,
3. which job is running,
4. which jobs failed or were canceled,
5. why an action is blocked,
6. how SAM2 and SAM3 choices affect the run, and
7. when it is safe to review, correct, and export.

Treat this as a severe product and software architecture repair, not a cosmetic card redesign. The current UI is experienced as unusable because possible jobs, active jobs, failed jobs, and next steps are not obvious enough. Do not solve this by adding more panels, subtitles, badges, or repeated explanatory text. Solve it by making the software state truthful, centralized, provider-neutral, and easy to follow.

The final product must work for SAM2 and SAM3. The user should not need to understand internal provider names, masks, trackers, or discovery modes to complete the normal path.

# Repository Context

Ground the work in this repository:

- https://github.com/ptse8204/json-animated-video
- Existing repo docs, README, examples, notebooks, tests, architecture, code style, and package scripts.
- Existing project discussions and instructions that define MotionJSON as a local-first object tracing application with review/correction/export as first-class product concepts.

Important current implementation areas to inspect before planning:

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/server.py`
- `src/motionjson/backend/jobs.py`
- `src/motionjson/backend/queue.py`
- `src/motionjson/backend/worker.py`
- `src/motionjson/backend/api.py`
- `src/motionjson/providers/`
- `src/motionjson/schemas/`
- `tests/`
- `scripts/check_local_ui_layout.mjs`
- `scripts/test_ui_config_builder.mjs`
- `notebooks/`
- `docs/`
- `README.md`
- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `codex_tasks.yaml`

Current intended user-facing workflow in docs:

```text
Choose goal -> Add/select video -> Connect model -> Prepare/run -> Review/export
```

Current intended review pipeline:

```text
Run discovery/trace -> review candidates -> keep candidates -> track selected -> review tracks -> correct if needed -> export reviewed objects
```

Observed risk areas to verify in the repo:

- The UI has both a 3-screen Setup/Prepare/Review structure and a hidden/parallel 5-step goal/video/model/prepare/review stepper. This can confuse the user's mental model.
- The UI currently has repeated goal choices in the sidebar and main goal cards, plus many cards and details panels competing for attention.
- Job state is split across job snapshots, progress, events, review payloads, artifacts, DOM classes, and local derived state.
- Some readiness is inferred from UI DOM status classes instead of a pure authoritative state selector.
- Provider display labels and provider IDs can be mixed in plan/status logic. Provider ID, connection ID, and display label must be separate.
- Synthetic/demo review tracks must never be presented as real backend results in normal mode. They may exist only as explicitly labeled preview estimates or debug mock behavior.
- Current docs may describe a guided flow, but Codex must inspect the running software and screenshot/layout behavior, not trust docs alone.

# Quality Priority

Quality is more important than speed. Prefer correctness, maintainability, validation, and useful product outcomes over rushing.

Do not merely make the UI look cleaner. The primary success metric is whether a first-time user can answer these questions at every moment:

- What task did I choose?
- What video am I using?
- Which provider/model will run?
- Is it SAM2, SAM3, hosted, local, or no-model?
- What will be sent to a hosted provider, if anything?
- What is the current job doing?
- Did it fail, succeed, or get canceled?
- What exact next action is available?
- Why is an action disabled?
- What output can I export now?

# Master Agent Operating Mode

Use one high-effort master Codex agent for this work.

The master agent owns:

- planning,
- implementation,
- validation,
- review,
- final decisions,
- commits,
- and final reporting.

Do not split planning, implementation, and review into separate full-context agents by default.

Use bounded read-only scouts only when independent critique materially improves quality. Scout prompts must be narrow and compact. Scouts must not edit files, install dependencies, format files, commit, change configuration, spawn other agents, or perform broad exploration without a concrete reason.

Recommended scouts:

- `plan-risk-scout`: before implementation of major architecture/UI phases.
- `diff-review-scout`: before committing a risky final diff.
- `test-gap-scout`: before committing lifecycle/state-machine changes.
- `adoption-scout`: after UI flow redesign to check whether a less technical user would understand it.

The master agent must synthesize scout feedback and make final decisions.

# Non-Negotiable Product Principles

1. One primary flow. Do not show competing Setup/Prepare/Review and 5-step models at the same level. Pick one visible mental model and keep the other only as internal implementation if still needed.
2. One primary action per screen. Secondary actions must be clearly secondary and local to the current step.
3. One source of truth for job state. UI job state must come from backend snapshots/events/review/export state through pure selectors, not DOM class scraping.
4. Provider-neutral model flow. SAM2 and SAM3 must use the same workflow contract: capability, prompt requirement, locality, hosted opt-in, run config, validation, job, review, export.
5. No fake confidence. Do not fabricate tracks, progress, candidates, or export readiness in normal mode. If a preview estimate is shown, label it as an estimate and keep it out of export readiness.
6. Plain-language failures. Every failed, blocked, or unavailable state must show what happened, why it matters, and the next recovery action.
7. Minimal UI copy. Avoid a card having both a title and a subtitle when four short choices are enough. Do not add repeated “helpful” text to every component. Use labels, status, and one concise reason.
8. Advanced stays advanced. Raw JSON, full route lists, provider internals, library internals, and debug tools should not compete with the normal path.
9. Hosted provider safety. Any hosted provider, SAM3/SAM2 hosted path, or planner must require explicit privacy/cost opt-in before network calls. Browser responses must not expose raw keys or local absolute paths.
10. Documentation must match reality. Update README, docs, notebooks, and troubleshooting after implementation, not before.

# Target User Flow

Implement the normal UI around this visible flow:

```text
Start
  -> Choose task
  -> Add video
  -> Choose model when required
  -> Prepare input
  -> Run
  -> Watch job
  -> Review result
  -> Export
```

## Start / Choose task

Show a compact task chooser with only these primary choices by default:

- Cut out one object
- Find by description
- Find moving things
- Import masks
- Review previous result

Move noisy/advanced variants behind an advanced disclosure:

- Trace all objects
- Discover objects / automatic proposals
- Propose all visible segments
- Find known classes
- Trace Everything

Do not duplicate the task chooser in both sidebar and main canvas. The sidebar may show the currently selected task and navigation, but not a second full picker.

## Add video

Show source status as a simple checklist:

- Local source registered
- Browser preview ready
- Rights metadata recorded

The primary action is `Add video` or `Use demo video`. When a preview is preparing, show the current state and block forward movement with one reason.

## Choose model

Only show this step if the selected workflow requires a model.

For each compatible connection show:

- name, e.g. `SAM2 local`, `Replicate SAM2 video`, `SAM3 local`, `Roboflow SAM3`, `Fal SAM3 image`, or `Custom SAM3 endpoint`,
- status: `Ready`, `Needs path`, `Needs key`, `Needs hosted confirmation`, `Installed but not runnable`, or `Unavailable`,
- one next action.

Do not expose raw internal names as the main label. Keep provider ID and display label separate in code.

Provider routing requirements:

- Cut out one object: prefer SAM2 local/hosted; allow SAM3 exemplar/box-first when compatible.
- Find by description: prefer SAM3 local/hosted concept workflow; keep detector fallback advanced.
- Find moving things: no model required; use motion foreground.
- Import masks: no model required; use external masks.
- Review previous result: no model required unless user chooses repair/rerun.

## Prepare input

Show only the inputs that matter for the chosen task:

- One object: object label plus point/box/brush tools. SAM3 single-object tracing should clearly require a box when that is the active engine.
- Find by description: one text prompt and optional max objects/quality advanced settings.
- Motion: sensitivity only if needed; otherwise use safe defaults.
- Import masks: mask directory/manifest.
- Review previous result: import/open path.

Show a readable run plan:

- task,
- video,
- model/provider,
- whether hosted calls are enabled,
- prompt requirements,
- review gate,
- estimated cost/privacy notes when applicable,
- validation blockers.

Raw config JSON must remain under Advanced.

## Run / Watch job

After starting a run, immediately move the user to a dedicated Job Center / Run Monitor state. This is the most important redesign.

The Job Center must be visible in the main flow, not only hidden in a right rail.

It must show:

- current selected job,
- active jobs count,
- recent jobs,
- status: queued/running/waiting for review/succeeded/failed/canceled,
- stage label,
- progress percentage when known,
- latest event message,
- elapsed time or created/updated time if available,
- provider/model used,
- cancel action when cancellable,
- retry action when failed and safe,
- open logs/details action.

Failed jobs must show:

- short failure headline,
- likely cause from events/review/fallback diagnostics/provider readiness,
- action to fix/retry,
- collapsible logs.

## Review result

The review flow should be explicit:

```text
Candidates -> Track selected -> Tracks -> Corrections -> Export
```

Do not make the user guess whether they are looking at candidates or tracks. If there are candidates but no tracks, the primary action should be `Track selected`. If there are tracks but no exportable reviewed objects, the primary action should be `Mark reviewed` or the exact missing action. If a job failed, do not show empty review UI as if the user did something wrong.

## Export

Export cards are allowed, but each card must have a single label, one status, one action, and one disabled reason. Do not add both title and subtitle unless they genuinely clarify a complex handoff.

# Required Architecture Direction

## Backend/API state contract

Add or formalize a single job lifecycle view that the frontend can consume. Suggested shape:

```json
{
  "jobId": "...",
  "projectId": "...",
  "type": "extract|track_selected|export|render|model_plan",
  "workflow": "trace_one_object|find_by_description|motion_foreground|external_masks|review_existing|...",
  "provider": {
    "id": "sam2-local",
    "label": "SAM2 local",
    "engine": "sam2",
    "locality": "local|hosted|no_model",
    "hostedCallsAllowed": false
  },
  "status": "queued|running|waiting_review|succeeded|failed|canceled",
  "phase": "setup|validating|queued|extracting|discovering|tracking|writing_artifacts|review_ready|exporting|complete|failed",
  "progress": {
    "percent": 0,
    "known": false,
    "label": "Preparing provider"
  },
  "latestEvent": {
    "type": "worker_claimed",
    "message": "worker claimed job",
    "createdAt": "..."
  },
  "failure": {
    "headline": "SAM3 model path is not configured",
    "reasonCode": "provider_unavailable",
    "message": "...",
    "suggestedAction": "Open Model Connections and save a SAM3 model path or choose hosted SAM3."
  },
  "review": {
    "candidateCount": 0,
    "selectedCandidateCount": 0,
    "trackCount": 0,
    "exportableTrackCount": 0,
    "needsReview": true
  },
  "actions": {
    "canCancel": true,
    "canRetry": false,
    "canReview": false,
    "canTrackSelected": false,
    "canExport": false
  }
}
```

This may be returned from one or more endpoints, but the frontend selector should consume a stable normalized shape. Candidate endpoints:

- `GET /api/workspace`
- `GET /api/progress?projectId=...`
- `GET /api/jobs?projectId=...`
- `GET /api/jobs/{jobId}`
- `GET /api/jobs/{jobId}/events`
- `GET /api/jobs/{jobId}/review`
- `GET /api/jobs/{jobId}/artifacts`
- `POST /api/jobs/{jobId}/track-selected`
- `POST /api/jobs/{jobId}/cancel`
- `POST /api/jobs/{jobId}/validate`
- `POST /api/jobs/{jobId}/exports`

The master agent should decide whether to extend an existing route or add a compact `jobCenter` block to `/api/workspace` and `/api/progress`. Avoid unnecessary new endpoints if existing endpoints can safely carry the normalized state.

## Frontend state architecture

Refactor enough of the UI so the normal flow is driven by pure selectors and event handlers, not incidental DOM state.

Suggested modules if feasible:

- `api_client.js` or equivalent API helpers.
- `workflow_state.js`: pure workflow machine and gating selectors.
- `job_lifecycle.js`: pure job normalization, progress, failure, and next-action selectors.
- `provider_connections.js`: provider compatibility and recommendation logic.
- `run_plan.js`: normalized run config and readable plan.
- `review_state.js`: candidates/tracks/export gates.
- `render.js` or view-specific render helpers.

Keep the static no-build architecture if that is the project convention, but reduce the monolithic `app.js` risk. If splitting files creates packaging/build risk, implement smaller pure functions inside existing files first, with tests.

## Provider-neutral SAM2/SAM3 contract

Create a clear separation between:

- `connectionId`, e.g. `sam3-hosted:roboflow-sam3-pcs`,
- `providerId`, e.g. `sam3-hosted`,
- `engine`, e.g. `sam3`,
- `displayLabel`, e.g. `Roboflow SAM3`,
- `workflow`, e.g. `find_by_description`,
- `capabilities`, e.g. supports concept, supports box, supports tracking, supports auto masks,
- `locality`, e.g. local/hosted/no-model,
- `readiness`, e.g. ready, needs_path, needs_key, needs_opt_in, unavailable.

Do not let display labels drive backend policy or status logic.

## No misleading fallback UI

Synthetic tracks, demo-only tracks, and inferred preview boxes must not be used as normal review truth. They may appear only when:

- debug mock mode is explicitly enabled, or
- they are clearly labeled as `Preview estimate` and not exportable.

Normal review truth must come from backend review payloads, artifacts, and track-selected responses.

# Roadmap

Codex must complete the phases below in order unless a real blocker is reached. Do not stop after one phase.

## Phase 0 — Baseline audit and reproducible failure map

Purpose: Verify the current unusable points from the actual running software.

User value: Ensures the redesign fixes observed behavior, not just documentation.

Technical scope:

- Run the UI locally with the project’s standard commands.
- Use the demo video path and at least one no-model path.
- Exercise at least: cut one object setup, model-required setup, no-model motion setup, failed/unavailable provider setup, job start, job failure or simulated failure, candidate review if available, export disabled state.
- Capture screenshots or text notes for the existing confusing states.
- Map which API routes are called for setup, jobs, progress, events, review, tracking, validation, and export.

Files/areas likely to change:

- `docs/roadmap/` new phase report only, unless immediate bugs block running.

Tests and validation:

- `python3 -m motionjson.cli backend diagnostics --json`
- `python3 -m motionjson.cli ui --no-open` or equivalent local command.
- `npm run ui:layout` when available.

Risk review:

- Do not change product behavior in this phase unless necessary to unblock the audit.
- Do not hide current issues.

Expected commit message:

- `docs: record local UI flow audit and job-state blockers`

## Phase 1 — Define authoritative job lifecycle and next-action contract

Purpose: Make the backend/frontend share one truthful representation of jobs, failures, review readiness, and actions.

User value: Users can finally see what is running, what failed, and what to do next.

Technical scope:

- Add pure backend helper(s) that derive a normalized job lifecycle view from job row, events, artifacts, review state, and validation/export state.
- Include active/recent job list in an existing workspace/progress response or add a minimal stable route if necessary.
- Ensure every job has: status, phase, latest event, progress, provider summary, failure summary, review summary, available actions.
- Preserve existing route compatibility.
- Ensure failed and canceled jobs remain visible in recent jobs with actionable messages.
- Ensure job progress does not claim precision when progress is unknown. Use `known: false` and conservative labels when only fallback progress exists.

Files/areas likely to change:

- `src/motionjson/ui/server.py`
- `src/motionjson/backend/jobs.py`
- `src/motionjson/backend/queue.py`
- `src/motionjson/backend/worker.py`
- tests under `tests/`
- schemas/docs if adding a response format.

Tests and validation:

- Existing Python tests discovered by repo.
- New tests for queued, running, succeeded, failed, canceled, no-progress, event-progress, candidate-only, track-ready, export-ready states.
- Validate no raw local storage keys or raw secrets leak in public response.

Risk review:

- Watch for breaking existing frontend consumers.
- Keep old fields until UI migration is complete.

Expected commit message:

- `feat(ui): add authoritative job lifecycle summaries`

## Phase 2 — Provider-neutral SAM2/SAM3 workflow contract

Purpose: Make SAM2/SAM3 selection predictable and safe across all workflows.

User value: Users can choose “local SAM2,” “hosted SAM2,” “local SAM3,” or “hosted SAM3” without the UI becoming a provider maze.

Technical scope:

- Centralize provider compatibility and recommendation logic.
- Separate connection ID, provider ID, engine, display label, hosted profile, capability flags, and readiness.
- Ensure SAM2 and SAM3 run-config generation uses the same normalized connection contract.
- Fix any status logic that compares display labels to provider IDs.
- Confirm hosted network/cost/privacy opt-ins are required and visible.
- Ensure no-model workflows bypass model setup cleanly.

Files/areas likely to change:

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/config_builder.js`
- `src/motionjson/ui/server.py`
- provider settings/model connector code
- tests for config builder and provider selection.

Tests and validation:

- JS tests for each workflow/provider combination.
- Backend run-config validation tests for SAM2 local/hosted, SAM3 local/hosted, motion, external.
- Hosted opt-in negative tests.

Risk review:

- Avoid silently changing actual provider behavior.
- Existing advanced detector workflows should remain available but not prominent.

Expected commit message:

- `fix(ui): normalize provider selection across SAM2 and SAM3`

## Phase 3 — Rebuild the visible workflow around one mental model

Purpose: Remove competing panels and make next steps obvious.

User value: First-time users can complete the workflow without guessing.

Technical scope:

- Choose one visible step model: Start / Video / Model / Prepare / Run / Review / Export, or an equivalent compact version.
- Remove duplicate goal pickers from the default visible UI. The sidebar should not repeat the main task picker.
- Move advanced choices to Advanced.
- Keep exactly one primary action per current screen.
- Make disabled primary action reasons visible and short.
- Make Run Monitor / Job Center part of the main flow after a job starts, not only a hidden details rail.
- Keep details rail for logs, artifacts, and advanced diagnostics only.
- Simplify card copy. Do not use title + subtitle + explanatory copy for simple choices.

Files/areas likely to change:

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/static/app.js`
- layout/screenshot tests.

Tests and validation:

- `npm run build`
- `npm run ui:layout`
- Screenshot or DOM assertions for default, source video, provider needed, prepare, running, failed, review, export states.
- Accessibility checks already present in layout script, plus keyboard traversal sanity.

Risk review:

- Avoid removing advanced functionality entirely; move it behind Advanced.
- Avoid introducing dependency-heavy frontend architecture unless repo already supports it.

Expected commit message:

- `feat(ui): simplify guided flow and expose job center`

## Phase 4 — Frontend state selectors and job center rendering

Purpose: Make the UI behavior robust and testable.

User value: The UI no longer lies, flickers, or presents stale/contradictory job state.

Technical scope:

- Implement pure selectors for workflow gate, primary action, job center, failure summary, review gate, export gate.
- Remove readiness/state derivation from DOM classes wherever practical.
- Render job list from normalized backend lifecycle state.
- Poll or refresh progress/events consistently. Avoid duplicate racing refreshes.
- Select the newest active job by default after starting a run, but preserve user-selected recent job when manually selected.
- Keep failed/canceled jobs visible and selectable.
- Add retry logic only when safe and explicit.

Files/areas likely to change:

- `src/motionjson/ui/static/app.js`
- new static helper modules if safe
- `scripts/test_ui_config_builder.mjs` or new JS tests.

Tests and validation:

- JS unit tests for selectors.
- Simulated job fixtures: no job, queued, running with progress event, failed with provider error, canceled, succeeded with candidates, succeeded with tracks, export-ready.
- `npm test`
- `npm run build`
- `npm run ui:layout`

Risk review:

- Watch for stale selected job/review/artifacts after polling.
- Avoid showing synthetic/demo tracks as real result.

Expected commit message:

- `refactor(ui): drive workflow from normalized state selectors`

## Phase 5 — Review, candidate tracking, correction, and export gates

Purpose: Make post-run work sequential and understandable.

User value: Users know whether they are reviewing candidates, tracking selected objects, correcting tracks, or exporting.

Technical scope:

- Render a compact post-run stage line: Candidates, Track selected, Tracks, Corrections, Export.
- If candidates exist and tracks do not, primary action should be `Track selected`.
- If no candidates or tracks exist after a completed job, show failure/diagnostic/retry guidance, not empty lists.
- Ensure `POST /api/jobs/{jobId}/track-selected` state updates the selected job review and job center correctly.
- Export disabled reasons must reference exact missing state: no completed run, no reviewed/exportable track, validation failed, pending correction, rights warning, etc.
- Keep correction tools available but not dominant unless a track is selected.

Files/areas likely to change:

- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.css`
- `src/motionjson/ui/server.py`
- review/export tests.

Tests and validation:

- Backend tests for review payload/candidate tracking/export validation.
- JS tests for review/export gate selectors.
- Layout smoke for review with candidates, review with tracks, failed job, export-ready.

Risk review:

- Preserve existing review payload contract.
- Make sure selected candidates are user-confirmed, not silently treated as final reviewed tracks.

Expected commit message:

- `feat(ui): clarify review tracking and export gates`

## Phase 6 — Documentation, README, notebooks, and system requirements

Purpose: Make onboarding match the software and reduce failed local setup.

User value: Users know what hardware they need, which path to choose, and how to recover.

Technical scope:

Update at least:

- `README.md`
- `docs/local_ui.md`
- `docs/first_run.md`
- `docs/run_local.md`
- `docs/run_free_instances.md`
- `docs/troubleshooting.md`
- `docs/provider_capabilities.md`
- `docs/security/api_keys.md` if hosted guidance changes
- relevant roadmap/status docs
- all relevant Colab notebooks under `notebooks/`

Documentation requirements:

- Explain the new flow with exact UI names.
- Include “Which path should I choose?” table:
  - CPU/no-model demo
  - local SAM2
  - hosted SAM2
  - local SAM3
  - hosted SAM3
  - motion foreground
  - external masks
- Add system requirements. Verify current dependencies and upstream/provider guidance before final wording. Use conservative language when requirements vary by model/checkpoint/video length.
- Recommended baseline guidance to refine and verify:
  - CPU/no-model/demo: 4 GB RAM minimum for tiny demo; 8 GB RAM recommended.
  - Local SAM2: 16 GB RAM minimum for small clips; 32 GB recommended; NVIDIA GPU with 8 GB VRAM minimum for small experiments; 12–16+ GB VRAM recommended for smoother local work; CPU is expected to be slow.
  - Local SAM3: 32 GB RAM recommended; modern NVIDIA GPU with 16+ GB VRAM recommended for local experiments unless verified otherwise; use hosted SAM3 when local GPU/RAM is insufficient.
  - Disk: 10–30 GB free for repo, venv, cached frames, outputs, and checkpoints; more for longer videos.
  - Short clips are strongly recommended for local first runs.
  - FFmpeg is needed for browser-safe previews and video render/export paths.
  - Python `>=3.10` per `pyproject.toml`; Node is needed for repo JS checks/build scripts.
- Colab notebooks must clearly separate no-model demo, local UI/provider connect, hosted keys, and heavy local SAM setup.
- Notebooks must warn users not to paste private videos or API keys into shared notebooks.
- Colab GPU/RAM limitations must be stated plainly. Hosted providers require explicit cost/privacy opt-in.
- Do not let docs claim SAM2/SAM3 is installed/runnable just because settings exist.

Files/areas likely to change:

- `README.md`
- `docs/**/*.md`
- `notebooks/*.ipynb`
- `docs/assets/` if screenshots are regenerated.

Tests and validation:

- Run docs link checks if available.
- Execute or at least structurally validate notebooks if practical.
- Run screenshot generation/check commands if docs assets changed.
- `npm run build`
- `npm run ui:layout`

Risk review:

- Avoid overstating local SAM3 requirements without verifying implementation/provider specifics.
- Avoid putting secrets or private paths into notebooks.

Expected commit message:

- `docs: update UI guidance notebooks and system requirements`

## Phase 7 — Regression coverage and release validation

Purpose: Prevent the UI from regressing back into unclear state.

User value: Future changes keep the workflow understandable and safe.

Technical scope:

- Add fixtures for lifecycle states and provider states.
- Add state selector tests.
- Add backend lifecycle tests.
- Add layout assertions for minimal UI copy, visible current job, failed job messaging, and one primary action per screen.
- Add docs/update tests as available.
- Regenerate docs screenshots only after UI stabilizes.
- Write a final audit report.

Files/areas likely to change:

- `tests/`
- `scripts/`
- `docs/design/`
- `docs/roadmap/`
- `docs/assets/`

Tests and validation:

Run discovered repo validation, expected to include:

```bash
python3 -m pytest
npm test
npm run lint
npm run build
npm run ui:layout
npm run embed:smoke
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --help
python3 -m motionjson.cli backend diagnostics --text
```

Also run any targeted tests added during the phases. If a command is unavailable, document why and use the closest repo-supported validation.

Risk review:

- Do not commit known failing validation unless explicitly creating a marked checkpoint commit.
- Ensure generated junk, screenshots, large outputs, local databases, API keys, checkpoints, and private videos are not committed.

Expected commit message:

- `test: cover guided UI lifecycle and job center states`

# Phase Execution Rules

For each phase Codex must:

1. Re-check the current repo state with `git status` and inspect relevant files.
2. Produce or update a concise phase plan.
3. Optionally spawn one bounded read-only plan-risk scout if the phase is complex or risky.
4. Implement the smallest correct version of the phase.
5. Run relevant tests, typecheck, lint, build, and behavior validation.
6. Optionally spawn one bounded read-only diff-review scout before committing.
7. Fix issues found by validation or scout review.
8. Rerun relevant validation.
9. Review the diff.
10. Commit the phase with the expected meaningful commit message.
11. Produce a concise phase summary.

Continue through all phases unless blocked by:

- missing credentials or secrets,
- destructive operations requiring user approval,
- ambiguous requirements that would cause major rework,
- validation failures that cannot be resolved safely,
- repository state that makes continuation unsafe.

If blocked, stop, explain the blocker clearly, and provide the smallest next action needed from the user.

# Git and Commit Policy

At the end of each completed phase:

- run `git status`,
- review the diff,
- ensure no secrets, credentials, generated junk, local database files, checkpoints, downloaded model weights, private videos, or unrelated files are included,
- run relevant validation,
- create one git commit for the phase,
- use a meaningful commit message that references the phase.

Do not commit if validation is failing unless the user explicitly asks for a checkpoint commit. If committing with known failures, clearly mark them in the commit message and final summary.

# Validation Policy

Discover and use the repo’s actual validation commands from package files, makefiles, CI configs, test configs, scripts, and documentation.

Validation may include:

- Python unit tests,
- backend API tests,
- job queue/worker tests,
- provider-readiness tests,
- UI selector tests,
- config-builder tests,
- layout/screenshot tests,
- build checks,
- lint checks,
- example smoke tests,
- rendering smoke tests,
- export verification,
- docs/notebook structural validation.

Do not paste full logs unless there is a failure. Summarize successful validation compactly.

# Scout Output Format

Every scout must return only:

- Scope inspected
- Files/symbols reviewed
- Findings
- Evidence
- Recommended action
- Confidence level

The master agent must synthesize scout output and decide what to do.

# UI Copy Rules for Codex

When generating user-facing UI or documentation, be selective and smart.

Do not generate repetitive cards like:

- title + subtitle + body for a four-choice picker,
- multiple badges saying the same thing,
- repeated “local-first” text on every panel,
- both a visible stepper and duplicate goal list,
- large advanced explanations in the normal path.

Preferred pattern for simple UI elements:

```text
Label
Status
One action
One disabled reason when blocked
```

Preferred pattern for complex states:

```text
What happened
Why it matters
What to do next
Details/logs collapsed
```

# Final Completion Criteria

Codex must not stop after only one phase. Continue until the full roadmap is complete or until a real blocker is reached.

Final Codex response must include:

- completed phases,
- commits created,
- files changed,
- validation performed,
- features added or improved,
- before/after summary of user flow,
- how SAM2 and SAM3 paths are handled,
- documentation/notebook updates,
- known risks,
- follow-up recommendations.

The final implementation is acceptable only if:

- the default UI has one clear normal path,
- the Job Center/Run Monitor is visible and understandable,
- active, failed, succeeded, and canceled jobs are obvious,
- failed jobs show recovery guidance,
- SAM2 and SAM3 provider choices use the same normalized workflow contract,
- no synthetic/demo tracks are shown as real results in normal mode,
- export gates explain exactly what is missing,
- README/docs/Colab notebooks match the implemented software,
- system requirements are documented,
- validation passes or any remaining failure is clearly justified as a blocker.
