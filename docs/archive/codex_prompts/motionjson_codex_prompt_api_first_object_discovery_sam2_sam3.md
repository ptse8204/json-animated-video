# Goal

Build MotionJSON into an API-first object discovery, tracking, and JSON motion-layer authoring tool where the default workflow is:

```text
Discover objects with low-cost clean settings
→ show API-returned object candidates
→ user selects the desired objects
→ backend tracks selected objects
→ export JSON-controlled reusable motion layers
```

The project must also offer advanced modes for maximum recall and Trace Everything, but those modes must be clearly marked as noisier, slower, and review-required. SAM2 should be used as the practical lower-cost default provider path when real model support is available. SAM3 should be added as an optional, capability-gated upgrade for concept, exemplar, and higher-recall discovery.

Do not implement this as a UI-only feature. The API/backend must be the source of truth for object candidates, tracks, diagnostics, correction history, artifacts, and export state. The UI must collect user intent, call the API, and render API results.

Repository: https://github.com/ptse8204/json-animated-video

# Repository Context

This project is MotionJSON / `json-animated-video`, a local-first tool for turning selected video objects into reusable JSON-controlled motion layers. The repo already has:

- a human-facing README with local UI, no-model quick start, red-ball demo, provider table, runtime/SDK notes, troubleshooting, and release-candidate boundaries;
- a local UI served through `python3 -m motionjson.cli ui --no-open --mock`;
- local UI API routes for capabilities, provider settings, run config validation, jobs, progress, review, artifacts, corrections, exports, and library workflows;
- provider settings for local/no-model providers, hosted providers, SAM2 local/hosted surfaces, OpenRouter, text detector, and class detector surfaces;
- `sam_auto_masks`, `text_detector`, and `class_detector` scaffolded/mock discovery paths;
- fallback diagnostics, track filtering, benchmark fixtures, runtime/SDK packages, and docs assets.

Current architectural direction for this roadmap:

1. **Default discovery should not require a text prompt.** Users should be able to click “Discover objects” and choose from a candidate gallery.
2. **Default discovery should optimize for low cost and fewer cleaner objects.** The first run should use limited keyframes, candidate caps, strict filtering, and selected-candidate tracking.
3. **Maximum recall should be an explicit advanced option.** It should allow more keyframes, more candidates, looser filters, and more noisy objects to filter.
4. **Trace Everything should be expert/experimental.** It should be bounded, review-required, and cost/noise warned.
5. **API-first is mandatory.** UI should render API data and must not fabricate final candidates/tracks/artifacts for normal job results.
6. **SAM2 vs SAM3 role split:**
   - SAM2 is the practical default for automatic keyframe proposals and video tracking once candidates are selected.
   - SAM3 is optional and capability-gated. It is best for concept prompts, exemplar search, and semantic/higher-recall discovery.

External model context to preserve:

- SAM2 supports automatic mask generation on images and a video predictor for promptable segmentation/tracking with multiple objects.
- SAM3 can detect, segment, and track objects in images/videos from text or visual prompts, and unlike SAM2 can exhaustively segment all instances of an open-vocabulary concept specified by text phrase or exemplars.
- SAM3 has heavier runtime requirements than the current MotionJSON CPU/mock path, so it must remain optional and capability-gated.
- Hosted SAM2/SAM3 must require explicit cost/privacy opt-in before network tests or hosted runs.

# Quality Priority

Quality is more important than speed.

Codex must prefer:

- correct API contracts;
- stable provider abstractions;
- honest capability diagnostics;
- low-cost defaults;
- clear review/export safety gates;
- maintainable code;
- repeatable tests;
- useful UX for nontechnical users;
- truthful documentation and screenshots.

Do not rush by only adding UI controls. The feature is incomplete until API, backend, UI, docs, tests, and validation are aligned.

# Master Agent Operating Mode

Use one high-effort master Codex agent for the actual software-engineering work.

The master agent owns:

- planning;
- implementation;
- validation;
- review;
- final decisions;
- commits;
- final phase summaries.

Do not split planning, execution, and review into separate full-context agents by default.

Use bounded read-only scouts only when independent critique materially improves quality. Keep scout prompts narrow and compact. Use at most 1–2 scouts per phase unless there is a specific high-risk reason.

Preferred scouts:

- `plan-risk-scout`: critiques architecture/product/test risk before implementation.
- `diff-review-scout`: reviews the final diff before commit.
- `test-gap-scout`: checks whether tests cover behavior, edge cases, and regressions.
- `rendering-scout`: checks rendering, animation, timeline, export, and media-generation correctness.
- `adoption-scout`: checks whether the feature is understandable to real users, especially less technical users.

Scouts must be read-only. They may inspect files, diffs, tests, and validation output. They must not edit files, install dependencies, change configuration, commit, or spawn more agents.

The master must synthesize scout feedback and make final decisions.

# Roadmap

## Phase OD-00 — Re-check repository state and API-first boundaries

### Purpose

Re-check the current repo state before implementation and verify where object discovery, provider settings, local UI API, authenticated API, worker execution, run config validation, review payloads, and frontend synthetic fallback logic currently live.

### User value

Prevents building the new object discovery flow on stale assumptions.

### Technical scope

Inspect:

- root README and docs index;
- `docs/local_ui.md`;
- `docs/discovery_providers.md`;
- `docs/provider_capabilities.md`;
- `docs/security/api_keys.md`;
- local UI server/API route handling;
- authenticated backend API;
- backend worker;
- run config model;
- provider settings;
- frontend config builder and review rendering;
- tests and CI config.

Identify exactly where the UI currently synthesizes tracks or review state and mark what must become demo-only.

### Files or areas likely to change

- `docs/roadmap/phase-od-00-report.md`
- possibly `docs/repo_status.md` if it is stale.

### Tests and validation

Run or discover actual validation commands. Start with:

```bash
python3 -m motionjson.cli --help
python3 -m motionjson.cli ui --help
python3 -m pytest -q
npm test
npm run lint
npm run build
```

Document any unavailable command honestly.

### Risk review

Use `plan-risk-scout` if repo state is ambiguous or if current UI/API boundaries differ from this prompt.

### Expected commit message

```text
phase od-00: audit object discovery architecture
```

---

## Phase OD-01 — Add object discovery quality presets to typed config

### Purpose

Create API-addressable object discovery presets:

- `clean`
- `balanced`
- `maximum_recall`
- `trace_everything`

### User value

Users get a low-cost default and a clear advanced path when the clean pass misses the desired object.

### Technical scope

Add a generic discovery mode:

```text
auto_object_proposals
```

Add config fields:

```json
{
  "qualityPreset": "clean",
  "intent": "discover_objects_clean",
  "providerPreference": "auto",
  "keyframePolicy": "scene_changes",
  "maxKeyframes": 3,
  "frameInterval": null,
  "maxCandidatesPerKeyframe": 32,
  "maxObjects": 12,
  "minMaskArea": 96,
  "maxMaskAreaRatio": 0.45,
  "dedupeIou": 0.78,
  "stabilityThreshold": 0.86,
  "motionScoreWeight": 0.35,
  "rejectWholeFrame": true,
  "rejectBackgroundLike": true,
  "trackSelectedOnly": true,
  "requireReview": true,
  "writeRejectedCandidates": true
}
```

Clean default values:

```json
{
  "qualityPreset": "clean",
  "maxKeyframes": 3,
  "maxCandidatesPerKeyframe": 32,
  "maxObjects": 12,
  "minMaskArea": 96,
  "maxMaskAreaRatio": 0.45,
  "dedupeIou": 0.78,
  "stabilityThreshold": 0.86,
  "trackSelectedOnly": true
}
```

Maximum recall defaults:

```json
{
  "qualityPreset": "maximum_recall",
  "maxKeyframes": 8,
  "frameInterval": 24,
  "maxCandidatesPerKeyframe": 128,
  "maxObjects": 64,
  "minMaskArea": 32,
  "maxMaskAreaRatio": 0.75,
  "dedupeIou": 0.9,
  "stabilityThreshold": 0.7,
  "trackSelectedOnly": true,
  "writeRejectedCandidates": true
}
```

Trace Everything must require explicit warning acknowledgement:

```json
{
  "qualityPreset": "trace_everything",
  "requireExplicitCostWarning": true,
  "trackSelectedOnly": false,
  "trackTopCandidates": true,
  "requireReview": true
}
```

### Files or areas likely to change

- `src/motionjson/config.py`
- `src/motionjson/providers/discovery.py`
- JSON schemas if present
- `tests/`
- `docs/run_config.md`
- `docs/discovery_providers.md`

### Tests and validation

Add tests for:

- valid clean preset;
- valid maximum recall preset;
- trace everything requires explicit acknowledgement;
- invalid candidate caps fail clearly;
- `trackSelectedOnly` defaults true for clean/balanced/maximum recall.

### Risk review

Use `plan-risk-scout` because this changes typed config and API contract.

### Expected commit message

```text
phase od-01: add object discovery quality presets
```

---

## Phase OD-02 — Add API-first candidate review schema

### Purpose

Define candidate review payloads that the UI can render without inventing results.

### User value

Users can browse discovered object candidates with confidence, warnings, thumbnails, and mask previews.

### Technical scope

Add a shared candidate shape:

```json
{
  "candidateId": "cand_001",
  "objectId": null,
  "label": "unlabeled object",
  "source": "auto_object_proposals",
  "providerName": "mock",
  "frameIndex": 0,
  "thumbnailArtifactId": "asset_thumb_001",
  "maskPreviewArtifactId": "asset_mask_001",
  "box": { "x": 120, "y": 80, "w": 96, "h": 72 },
  "areaRatio": 0.08,
  "stabilityScore": 0.88,
  "motionScore": 0.64,
  "confidence": 0.83,
  "frameCoverageEstimate": 0.72,
  "warnings": [],
  "rejectionReason": null,
  "defaultSelected": true,
  "reviewStatus": "pending"
}
```

Add candidate summary:

```json
{
  "candidateCount": 37,
  "acceptedCandidateCount": 18,
  "rejectedCandidateCount": 19,
  "defaultSelectedCount": 10,
  "rejectionReasons": {
    "too_small": 5,
    "duplicate_mask": 8,
    "whole_frame": 2,
    "background_like": 4
  },
  "qualityPreset": "clean",
  "providerName": "mock",
  "requiresReview": true
}
```

Make `GET /api/jobs/{jobId}/review` return candidates and summary when discovery artifacts exist.

### Files or areas likely to change

- backend review metadata code
- artifact registration
- local UI server
- authenticated API if present
- tests
- docs

### Tests and validation

Tests for:

- candidate summary shape;
- redaction of paths/secrets;
- rejected candidates included when configured;
- UI/API response includes no storage keys;
- docs link tests.

### Risk review

Use `diff-review-scout` before commit.

### Expected commit message

```text
phase od-02: add api-first candidate review schema
```

---

## Phase OD-03 — Add deterministic mock object discovery provider

### Purpose

Implement a no-model mock provider for object discovery that writes real candidate artifacts and review payloads.

### User value

Users and CI can test the full discovery → review → selection flow without SAM2/SAM3, GPU, model files, or hosted credentials.

### Technical scope

Add a mock provider for:

```text
auto_object_proposals + qualityPreset clean/balanced/maximum_recall
```

The mock provider should produce:

- candidate masks;
- thumbnails or preview overlays;
- candidate summary;
- rejected candidates;
- deterministic scores;
- no AI/network usage.

### Files or areas likely to change

- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/mocks.py`
- backend worker
- artifact helpers
- tests
- docs/examples

### Tests and validation

Tests for:

- deterministic candidate output;
- clean preset returns fewer candidates than maximum recall;
- rejected candidates are recorded;
- candidate caps are honored;
- no-model path works in CI.

### Risk review

Use `test-gap-scout`.

### Expected commit message

```text
phase od-03: add mock object discovery provider
```

---

## Phase OD-04 — Add selected-candidate tracking API

### Purpose

Let users select candidates from the gallery, then track/export only the selected objects by default.

### User value

Keeps cost low and avoids wasting compute on noisy proposals.

### Technical scope

Add local UI API route:

```text
POST /api/jobs/{jobId}/track-selected
```

Payload:

```json
{
  "candidateIds": ["cand_001", "cand_004"],
  "trackMode": "selected_only",
  "exportReviewRequired": true
}
```

Add authenticated/headless API equivalent, for example:

```text
POST /v1/extraction-runs/{runId}/track-selected
```

Behavior:

- validate that candidate IDs belong to the job;
- create selected object specs;
- track selected candidates only;
- write tracks, scene graph, masks, cutouts, diagnostics;
- return updated review and artifacts;
- keep auto-discovered exports gated by review.

### Files or areas likely to change

- local UI server
- backend API
- worker/job model
- corrections/review state
- tests
- docs

### Tests and validation

Tests for:

- invalid candidate IDs;
- selected-only tracking;
- review gate;
- artifact registration;
- API redaction.

### Risk review

Use `plan-risk-scout` because this creates a new API flow.

### Expected commit message

```text
phase od-04: add selected candidate tracking API
```

---

## Phase OD-05 — Make UI render API candidates only

### Purpose

Move the UI toward the project’s desired architecture: UI uses API and shows API results.

### User value

Users see trustworthy results, not estimated or fabricated tracks.

### Technical scope

Add UI candidate browser:

- candidate gallery/list;
- mask overlay thumbnail;
- keep/ignore checkbox;
- filters: selected, stable, moving, not background, not duplicate, min frame coverage;
- quality preset selector: Clean / Balanced / Maximum Recall;
- advanced Trace Everything disclosure;
- Track selected button.

Remove or isolate synthetic final track generation. If retained for demos, it must be explicitly:

```json
{
  "demoMode": true,
  "source": "demo-only",
  "exportable": false
}
```

The normal UI must render:

- candidates from API review payload;
- tracks from API review payload;
- fallback diagnostics from API;
- artifacts from API;
- correction history from API;
- export eligibility from API validation.

### Files or areas likely to change

- `src/motionjson/ui/static/index.html`
- `src/motionjson/ui/static/app.js`
- `src/motionjson/ui/static/app.css`
- JS tests
- UI layout smoke checks
- docs screenshots

### Tests and validation

Tests for:

- config builder includes quality presets;
- candidate browser renders API payload;
- no synthetic final tracks in normal completed job state;
- Track selected calls API route;
- layout smoke passes.

### Risk review

Use `rendering-scout` or `diff-review-scout`.

### Expected commit message

```text
phase od-05: add api-rendered object discovery browser
```

---

## Phase OD-06 — Add SAM2 automatic proposal adapter

### Purpose

Wire a real optional SAM2 automatic mask proposal path for keyframes.

### User value

Advanced/local users can run real low-cost object discovery without text prompts.

### Technical scope

Implement adapter around SAM2 automatic mask generation on selected keyframes and SAM2 video propagation for selected candidates when dependencies/model paths are configured.

Do not make SAM2 a default install dependency. Keep it optional and capability-gated.

Key behaviors:

- sample keyframes according to preset;
- run automatic mask generation on keyframes;
- filter/dedupe proposals;
- save candidates and rejected candidates;
- track selected candidates through video;
- write diagnostics and resource profile;
- never silently claim SAM2 is ready if package/checkpoint/config/device are missing.

### Files or areas likely to change

- provider settings/capabilities
- SAM2 provider adapter
- discovery providers
- backend worker
- docs
- tests with mocks

### Tests and validation

No real GPU/model required in CI. Add mocked SAM2 adapter tests for:

- dependency missing diagnostics;
- model path validation;
- keyframe caps;
- candidate filtering;
- selected tracking.

### Risk review

Use `plan-risk-scout` and `test-gap-scout`.

### Expected commit message

```text
phase od-06: add optional sam2 automatic proposal adapter
```

---

## Phase OD-07 — Add SAM3 provider diagnostics and mock modes

### Purpose

Add SAM3 as an optional provider family without requiring SAM3 installation.

### User value

Users can understand whether SAM3 is available and can test the UI/API flow through mock modes.

### Technical scope

Add provider IDs:

```text
sam3-local
sam3-hosted
sam3-concept
sam3-exemplar
sam3-auto-masks
```

Add discovery modes:

```text
sam3_concept
sam3_exemplar
sam3_auto_masks
```

Add mock implementations for:

- concept discovery;
- exemplar discovery;
- SAM3-style auto proposal discovery.

### Files or areas likely to change

- `src/motionjson/provider_settings.py`
- `src/motionjson/capabilities.py`
- config/discovery providers
- tests
- docs

### Tests and validation

Tests for:

- SAM3 providers show missing dependency/model/credential status;
- mock SAM3 concept/exemplar works without model;
- hosted credentials are redacted;
- hosted setup tests do not make network calls unless explicitly requested.

### Risk review

Use `diff-review-scout`.

### Expected commit message

```text
phase od-07: add optional sam3 provider diagnostics and mocks
```

---

## Phase OD-08 — Add real SAM3 local adapter behind capability gates

### Purpose

Support SAM3 local execution when the user has compatible environment and model access.

### User value

Advanced users can use SAM3 for concept/exemplar/higher-recall discovery.

### Technical scope

Add optional dependency handling for SAM3. Do not break the base install.

Adapter should support, when available:

- concept prompt discovery;
- exemplar/crop discovery;
- video session tracking;
- one-frame smoke test;
- candidate/track outputs in MotionJSON’s shared API format.

Expected SAM3 strengths to expose:

- “Trace by concept”;
- “Find objects like this”;
- higher-recall semantic discovery.

### Files or areas likely to change

- optional dependencies in `pyproject.toml`;
- provider adapter module;
- model connection UI/backend tests;
- capability diagnostics;
- docs.

### Tests and validation

CI should use mocked SAM3. Real SAM3 local tests must be optional and skipped unless environment variables/model paths are present.

### Risk review

Use `plan-risk-scout`; this is high-risk because SAM3 has heavier runtime requirements.

### Expected commit message

```text
phase od-08: add optional local sam3 adapter
```

---

## Phase OD-09 — Add hosted SAM3 adapter with explicit cost/privacy opt-in

### Purpose

Let users test SAM3-compatible hosted endpoints from the UI/API without leaking secrets or accidentally sending frames.

### User value

Users without local GPU/model setup can test SAM3-like providers safely.

### Technical scope

Add hosted endpoint contract:

- endpoint URL;
- API key;
- model name;
- setup-only test with no network;
- explicit one-frame smoke test with network opt-in;
- timeouts/retries;
- redaction;
- cost/privacy warnings;
- no client-side secrets.

### Files or areas likely to change

- provider settings
- hosted provider adapter
- API routes for model tests
- tests
- docs/security/api_keys.md

### Tests and validation

Tests for:

- no-network setup test;
- explicit opt-in required for network test;
- redaction;
- invalid endpoint/key;
- response schema validation.

### Risk review

Use `plan-risk-scout` and `diff-review-scout`.

### Expected commit message

```text
phase od-09: add hosted sam3 adapter
```

---

## Phase OD-10 — Add Trace Everything expert mode

### Purpose

Provide the aggressive “as much as possible” mode while keeping the default clean and affordable.

### User value

Power users can recover missed objects when clean discovery is too conservative.

### Technical scope

Trace Everything must:

- require explicit user acknowledgement;
- use caps;
- write rejected candidates;
- show cost/noise warning;
- require review before export;
- default to selected tracking when possible, or top-candidate preview if explicitly enabled.

### Files or areas likely to change

- config
- API validation
- UI controls
- backend worker
- docs
- tests

### Tests and validation

Tests for:

- warning acknowledgement required;
- caps enforced;
- export blocked before review;
- rejected candidates shown.

### Risk review

Use `adoption-scout` to check user copy and safety.

### Expected commit message

```text
phase od-10: add trace everything expert mode
```

---

## Phase OD-11 — Improve JSON animation/motion schema for discovered candidates

### Purpose

Make discovered/tracked candidates first-class MotionJSON objects with stable review metadata.

### User value

Exports become easier to consume, debug, and reuse in websites/editors.

### Technical scope

Add or refine schema fields for:

- candidate source;
- discovery preset;
- provider/model;
- candidate score;
- user review status;
- filter/rejection reason;
- selected/ignored state;
- track confidence;
- motion coverage;
- rights/lineage metadata;
- correction history reference.

### Files or areas likely to change

- schemas
- validation
- exporters
- runtime/SDK docs
- tests

### Tests and validation

Tests for:

- schema validation;
- backward compatibility;
- runtime can ignore unknown future fields;
- SDK parses candidate/review metadata.

### Risk review

Use `test-gap-scout`.

### Expected commit message

```text
phase od-11: extend motionjson schema for discovery metadata
```

---

## Phase OD-12 — Timeline/keyframe authoring and preview reliability

### Purpose

Let users refine discovered objects across time and preview motion layers reliably.

### User value

MotionJSON becomes more useful as an authoring tool, not only an extraction tool.

### Technical scope

Add:

- keyframe selection for discovery;
- scene-change keyframe suggestions;
- timeline markers for candidate appearance/loss;
- preview scrub reliability;
- review overlays from API tracks;
- correction affordances for split/merge/relabel/hide/export.

### Files or areas likely to change

- UI
- API review/correction routes
- runtime preview
- tests
- docs/screenshots

### Tests and validation

Use rendering/layout tests and browser smoke tests.

### Risk review

Use `rendering-scout`.

### Expected commit message

```text
phase od-12: improve discovery timeline authoring
```

---

## Phase OD-13 — Export workflows and templates

### Purpose

Make selected discovered objects easy to ship as JSON motion layers.

### User value

Users can take discovered objects into websites/editors with less friction.

### Technical scope

Add or improve:

- website ZIP export for selected objects;
- manifest snippets;
- object-layer pack templates;
- runtime examples;
- Remotion plan improvements if appropriate;
- export validation messages for unreviewed auto-discovered objects.

### Files or areas likely to change

- exporters
- runtime/SDK packages
- examples
- docs
- tests

### Tests and validation

Run:

```bash
npm test
npm run embed:smoke
python3 -m pytest -q
```

Add export-specific tests.

### Risk review

Use `rendering-scout` for preview/export correctness.

### Expected commit message

```text
phase od-13: improve selected object export workflows
```

---

## Phase OD-14 — Documentation, screenshots, benchmarks, and release polish

### Purpose

Make the feature understandable and trustworthy for users.

### User value

Users know which mode to choose, what it costs, what SAM2/SAM3 can and cannot do, and how to recover when results are noisy.

### Technical scope

Update:

- README;
- docs index;
- local UI docs;
- discovery provider docs;
- provider capability docs;
- SAM2/SAM3 docs;
- security/API key docs;
- troubleshooting;
- screenshots;
- benchmark fixtures;
- release checklist.

Docs must explain:

- Clean discovery is default.
- Maximum recall is advanced.
- Trace Everything is expert/experimental.
- SAM2 is the practical low-cost default when configured.
- SAM3 is optional and best for concept/exemplar discovery.
- Export requires review for auto-discovered candidates.
- UI renders API results.

### Files or areas likely to change

- `README.md`
- `docs/*.md`
- `docs/assets/*`
- `scripts/capture_docs_assets.py`
- tests for docs/assets/links

### Tests and validation

Run:

```bash
python3 scripts/capture_docs_assets.py --check
python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q
npm run ui:layout -- --check
git diff --check
```

### Risk review

Use `adoption-scout`.

### Expected commit message

```text
phase od-14: document object discovery workflows
```

---

# Phase Execution Rules

For each phase, Codex must:

1. Re-check the current repo state.
2. Produce or update a concise phase plan.
3. Optionally spawn a read-only `plan-risk-scout` if the phase is complex, risky, or changes architecture/API behavior.
4. Implement the smallest correct version of the phase.
5. Run relevant tests, typecheck, lint, build, docs checks, rendering smoke tests, and behavior validation.
6. Optionally spawn a read-only `diff-review-scout`, `test-gap-scout`, `rendering-scout`, or `adoption-scout` before committing.
7. Fix any issues found.
8. Rerun relevant validation.
9. Run `git status --short`.
10. Review the diff and ensure no secrets, credentials, generated junk, or unrelated files are included.
11. Commit the phase with the expected phase commit message.
12. Produce a concise phase summary.

Codex must continue through the roadmap until all planned phases are complete, unless blocked by:

- missing credentials or secrets;
- destructive operations requiring user approval;
- ambiguous product requirements that would cause major rework;
- validation failures that cannot be resolved safely;
- repository state that makes continuation unsafe.

If blocked, Codex must stop, explain the blocker clearly, and provide the smallest next action needed from the user.

# Git and Commit Policy

At the end of each completed phase:

```bash
git status --short
git diff --check
git add <phase files>
git commit -m "<phase commit message>"
```

Before committing:

- review all changed files;
- ensure no secrets or local credentials are included;
- ensure generated artifacts are intentional, deterministic, small, and documented;
- ensure docs do not overclaim SAM2/SAM3 capabilities;
- ensure validation passes.

Do not commit if validation is failing unless the user explicitly asks for a checkpoint commit. If committing with known failures, clearly mark them in the commit message and phase summary.

# Validation Policy

Codex should discover and use the repo’s actual validation commands from package files, CI config, tests, and docs.

Prefer these when available:

```bash
python3 -m motionjson.cli --help
python3 -m motionjson.cli extract --help
python3 -m motionjson.cli backend --help
python3 -m motionjson.cli ui --help
python3 -m motionjson.cli benchmark --help
python3 -m pytest -q
npm test
npm run lint
npm run build
npm run embed:smoke
npm run ui:layout -- --check
python3 scripts/capture_docs_assets.py --check
git diff --check
```

Validation may include:

- unit tests;
- integration tests;
- type checks;
- lint;
- static UI build;
- browser/rendering smoke tests;
- animation/timeline regression tests;
- export verification;
- docs link checks;
- docs asset checks;
- example validation;
- package dry runs;
- Docker smoke checks.

Do not paste full logs unless there is a failure. Summarize successful validation compactly.

# Scout Output Format

Every scout must return only:

```text
- Scope inspected
- Files/symbols reviewed
- Findings
- Evidence
- Recommended action
- Confidence level
```

The master agent must synthesize the scout output and decide what to do.

Scouts must not edit files, format files, install dependencies, commit, change config, spawn more agents, or perform broad repo exploration without a concrete reason.

# Final Completion Criteria

The generated Codex prompt must tell Codex not to stop after only one phase. Codex should continue until the roadmap is complete or until a real blocker is reached.

The final Codex response should include:

- completed phases;
- commits created;
- files changed;
- validation performed;
- features added or improved;
- known risks;
- follow-up recommendations.

The feature is not complete until:

- clean discovery is the default;
- maximum recall exists as an advanced option;
- Trace Everything is explicit and review-gated;
- API owns candidates/tracks/diagnostics/artifacts/export state;
- UI renders API results and does not fabricate normal completed job outputs;
- selected-candidate tracking works;
- SAM2 automatic proposal support is optional and capability-gated;
- SAM3 concept/exemplar support is optional and capability-gated;
- hosted providers require explicit cost/privacy opt-in;
- docs, screenshots, examples, tests, and validation are updated.
