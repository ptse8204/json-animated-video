# MotionJSON / json-animated-video — Codex Future Plan with Commercial Local UI Redesign

This file is the active Codex-processable implementation brief for this repository. It includes a commercialization-grade Local UI redesign track, visual-regression expectations, and a bring-your-own-key model/provider configuration track.

Repository: `https://github.com/ptse8204/json-animated-video`

---

## Codex Goal

Use this as the active Codex Goal:

```text
/goal Turn MotionJSON into a human-onboardable, local-first, commercialization-ready video object-layer editing product, verified by a rewritten public README, local/free run paths, screenshots/demos, CI-safe smoke tests, a redesigned non-cluttered Local UI, visual-regression evidence, and phase reports for every completed phase, while preserving CLI compatibility, optional heavy ML dependencies, CPU/mock/no-model operation, clear provider diagnostics, and secure bring-your-own-key model/provider configuration. Use the repo, existing AGENTS.md/CODEX_MASTER_PROMPT.md/codex_tasks.yaml/docs, and local test outputs as evidence. Continue phase by phase until all phases below are complete; if a phase is blocked, commit the completed safe slice, write the blocker and unlock condition in the phase report, and continue only when the blocker is resolved.
```

---

## Commercialization-grade Local UI mandate

The current Local UI must be treated as unacceptable for a future commercial product if it has cluttered panels, overlapping menus, weak hierarchy, unclear navigation, cramped controls, or confusing setup flows. Do not limit this work to cosmetic CSS tweaks. The redesign must produce a coherent product shell and workflow that a less-technical user could understand.

Non-negotiable product requirements:

- Build a clear application frame: top bar, left navigation or project rail, main workspace, right inspector, bottom timeline/job status area where appropriate.
- Prevent layout collisions: no overlapping dropdowns, floating menus, modals, or panels at common viewport sizes.
- Support responsive breakpoints for laptop, desktop, and narrow tablet widths.
- Define design tokens for spacing, typography, border radius, z-index, shadow, panel elevation, focus rings, and status colors instead of ad hoc CSS.
- Add a component inventory for buttons, inputs, cards, tabs, drawers, dialogs, menu/dropdown, toast, progress/status, provider cards, timeline controls, object candidate rows, and preview canvas shell.
- Add empty, loading, error, disabled, offline, and no-provider states for every major screen.
- Add keyboard and accessibility basics: focus order, visible focus states, labels, dialog focus trapping, escape-to-close behavior, ARIA only where appropriate, and color-contrast checks.
- Add visual regression or screenshot smoke tests for the main Local UI screens.
- Add real screenshots before and after the redesign.
- Treat the UI as a product surface, not a developer debug page.

Commercial UX target:

- A new user should understand in under 60 seconds where to create a project, add a video, choose a provider/model, enter credentials if needed, start extraction, review objects, correct errors, preview the output, and export.
- An advanced user should still be able to inspect provider diagnostics, logs, JSON manifests, benchmark details, and exact export settings without cluttering the default flow.

---

## Codex skill requirements for UI/product work

Before starting any Local UI redesign, Codex must check which skills are available. If the correct skill exists, explicitly use it. If it does not exist, Codex must create or request an appropriate skill instead of improvising a one-off redesign.

Required skill intent, by name if present:

- `$frontend-design-system` or `$ui-design-system`: use for layout hierarchy, component system, spacing, typography, design tokens, reusable UI primitives, and commercial polish.
- `$responsive-layout-debugging` or `$layout-overlap-debugger`: use for detecting and fixing overlapping menus, panels, dropdowns, modals, z-index bugs, and viewport breakage.
- `$visual-regression-testing` or `$screenshot-regression`: use for Playwright/screenshot capture, before/after comparisons, and preventing future UI regressions.
- `$accessibility-audit` or `$a11y-audit`: use for keyboard navigation, focus behavior, labels, color contrast, and dialog/menu accessibility.
- `$product-ux-review` or `$adoption-scout`: use to judge whether the UI helps less technical users and whether the product is commercially understandable.
- `$provider-settings-security` or `$secrets-handling`: use for API key entry, local storage, redaction, environment-variable precedence, and model/provider selection safety.
- `$figma-design-translation` if a Figma file or screenshots are used as source material.

If these skills do not exist:

1. Search available skills via Codex skill discovery. In CLI/IDE, use `/skills` or explicit `$skill-name` discovery if available. Also inspect repo-local `.agents/skills/`, user-level skills, and any project guidance in `AGENTS.md`.
2. Use `$skill-creator` if available to create repo-local skills under `.agents/skills/`, because UI/product redesign and BYOK provider settings will recur across future phases.
3. If `$skill-creator` is not available, create the skills manually as `SKILL.md` files with clear metadata and concise triggers.
4. Commit repo-specific skills only when they are useful to this repository and do not include personal credentials, private notes, or environment-specific paths.

Minimum repo-local skills to add if missing:

```text
.agents/skills/motionjson-commercial-ui/SKILL.md
.agents/skills/motionjson-visual-regression/SKILL.md
.agents/skills/motionjson-provider-settings-security/SKILL.md
```

The master agent remains responsible for final decisions. Skills and scouts provide workflow discipline, critique, and validation, but do not replace master ownership.

---

## Master-agent operating model

You are the Master Agent. Planning should use the highest reasoning effort. Execution and review agents may use lower effort unless the phase is high-risk.

Read these files first, if present:

- `AGENTS.md`
- `CODEX_MASTER_PROMPT.md`
- `codex_tasks.yaml`
- `docs/index.md`
- `docs/first_run.md`
- `docs/local_ui.md`
- `docs/deployment.md`
- `docs/migration_and_known_limitations.md`
- `README.md`
- `README_old.md`
- `pyproject.toml`
- `package.json`
- `Dockerfile`

Spawn or emulate these subagents:

- `repo_archaeologist`: map actual repo state, commands, dependencies, tests, missing files, stale docs, and generated artifacts.
- `product_strategist`: clarify user personas, product framing, homepage copy, adoption path, and roadmap priorities.
- `docs_devrel_engineer`: rewrite README/docs in a human voice; add screenshots, walkthroughs, demos, troubleshooting, and copy-editing.
- `frontend_ui_engineer`: improve local UI discoverability, screenshot readiness, demo flows, and frontend smoke tests.
- `commercial_ui_designer`: create the commercial-grade information architecture, design system, layout rules, component inventory, and UX acceptance criteria.
- `layout_regression_engineer`: build Playwright/screenshot/viewport checks to catch overlapping panels, menus, dropdowns, modals, z-index issues, and responsive breakage.
- `backend_cv_architect`: improve provider capability checks, local/free providers, segmentation/tracking pipeline, exports, and diagnostics.
- `model_provider_architect`: design provider registry, user-supplied API key flow, model picker, capability metadata, cost warnings, and local/hosted model routing.
- `security_privacy_architect`: review API key handling, secret redaction, environment-variable fallback, local-only persistence, logging safety, and hosted-demo restrictions.
- `qa_benchmark_engineer`: add tests, deterministic fixtures, screenshot/demo generation, smoke scripts, and CI coverage.
- `release_packaging_engineer`: add devcontainer/Codespaces, Docker, packaging, release, and hosted-demo paths.
- `reviewer`: inspect every phase diff for correctness, overclaims, missing tests, broken docs, and regressions before commit.

Mandatory loop for every phase:

1. Start from a clean working tree or document why it is not clean.
2. Master Agent announces the phase objective.
3. Spawn relevant subagents.
4. Consolidate their findings into a concrete implementation checklist.
5. Implement the smallest coherent slice that satisfies the phase.
6. Run relevant tests/smoke commands.
7. Spawn `reviewer` and fix material findings.
8. Write `docs/roadmap/phase-XX-report.md` with summary, changed files, tests, screenshots/demos produced, known limitations, and follow-ups.
9. End with:

```bash
git status --short
git add <phase files>
git commit -m "phase XX: <short description>"
```

Do not skip commits. Do not stop after a frontend-only pass. Continue until all planned phases are complete.

---

## Phase 00 — Repo archaeology and truthful status baseline

**Goal:** Establish what is actually implemented and what is only planned.

**Subagents:** `repo_archaeologist`, `qa_benchmark_engineer`, `reviewer`

**Tasks:**

- Inspect top-level files, source tree, tests, docs, scripts, and tracked outputs.
- Run or attempt:

```bash
python -m motionjson.cli --help
python -m motionjson.cli backend --help
python -m motionjson.cli ui --help
python -m pytest -q
npm run build
npm test
npm run lint
```

- Record commands that fail and why. Do not pretend they passed.
- Audit docs for overclaiming: every README/product claim must map to a command, test, demo, or clearly marked roadmap item.
- Identify generated artifacts that should not be tracked, especially `out/` content, unless intentionally preserved as a tiny demo.

**Deliverables:**

- `docs/roadmap/phase-00-report.md`
- Optional: `docs/repo_status.md` with “implemented / partially implemented / planned” table.

**Acceptance:**

- Codex can answer “what exists today?” without guessing.
- No code behavior is changed unless a tiny fix is required to run basic help/tests.

**Commit:** `phase 00: audit repository status`

---

## Phase 01 — Rewrite public README for humans

**Goal:** Make the public landing page useful to a new user in the first 60 seconds.

**Subagents:** `product_strategist`, `docs_devrel_engineer`, `reviewer`

**Important instruction:** The README must sound human. Avoid robotic phrases like “this repository implements a pipeline.” Explain what problem the tool solves, who it is for, and what a user can try immediately. Use the older README as source material, but verify every claim against the current repo.

**Tasks:**

- Replace the current root `README.md` Codex-packet framing with a user-facing README.
- Move the current Codex packet text into `docs/codex/planning_packet.md` or keep it in a clearly labeled Codex docs page.
- Merge useful parts of `README_old.md` into the new README.
- Add these sections:
  - What MotionJSON is.
  - What it is not: not full “video to JSON/SVG/Lottie”; raster/alpha assets are controlled by compact JSON.
  - Who it is for: creators, web developers, editors, motion designers, ML/CV experimenters.
  - 30-second local UI quick start.
  - CLI red-ball demo.
  - Docker/API run path.
  - Free hosted/dev options: Codespaces, Colab CLI demo, Hugging Face Space plan.
  - Screenshots and demos.
  - Troubleshooting and provider diagnostics.
  - Roadmap and limitations.
  - Contributing with Codex.
- Add repo metadata recommendations in `docs/repo_status.md`: GitHub About description, website, topics, release status.

**Screenshots/demos required:**

Create `docs/assets/README_ASSETS.md` listing required assets and how to regenerate them. Prefer actual screenshots over placeholders.

Minimum assets:

- `docs/assets/local-ui-first-run.png`
- `docs/assets/local-ui-new-project.png`
- `docs/assets/local-ui-extraction-wizard.png`
- `docs/assets/local-ui-provider-diagnostics.png`
- `docs/assets/local-ui-job-review.png`
- `docs/assets/canvas-preview-red-ball.png`
- Optional GIF/video: `docs/assets/red-ball-demo.gif` or `docs/assets/red-ball-demo.mp4`

If screenshot automation is not ready, add temporary marked placeholders only in `docs/assets/README_ASSETS.md`, not fake screenshots.

**Acceptance:**

- README is useful to non-expert users.
- README includes pictures or clearly documented commands to generate them.
- README does not overclaim unsupported ML features.
- Codex docs are not lost; they are moved out of the public landing page.

**Commit:** `phase 01: rewrite public README`

---

## Phase 02 — First-run automation and local/free run paths

**Goal:** Make local and free-instance setup copy-pasteable.

**Subagents:** `release_packaging_engineer`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`

**Tasks:**

- Add scripts:
  - `scripts/first_run_local.sh`
  - `scripts/first_run_local.ps1`
  - `scripts/run_local_ui_mock.sh`
  - `scripts/run_red_ball_demo.sh`
  - `scripts/run_backend_api.sh`
- Add docs:
  - `docs/run_local.md`
  - `docs/run_free_instances.md`
- Local docs must cover:
  - Python venv install.
  - CPU/mock/no-model UI.
  - CLI red-ball demo.
  - local API.
  - Docker and Docker Compose.
- Free instance docs must cover:
  - GitHub Codespaces using CPU/mock mode.
  - Google Colab for CLI demos, with warning that Colab is not suitable for long-running web service hosting.
  - Hugging Face Spaces as a future hosted demo target, preferably CPU Basic/mock mode first.
- Add `.devcontainer/devcontainer.json` with Python, Node, ffmpeg, and post-create install command.
- Keep default install CPU-friendly.

**Acceptance:**

- A new user can run local UI with one script or four commands.
- A Codespaces user can open the repo and run CPU/mock UI.
- Colab instructions run CLI demos without pretending to be production hosting.
- All scripts are documented and tested where feasible.

**Commit:** `phase 02: add first-run scripts and free instance docs`

---

## Phase 03 — Screenshots, GIFs, and demo generation

**Goal:** Make the README visually convincing and easy to trust.

**Subagents:** `frontend_ui_engineer`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`

**Tasks:**

- Add screenshot automation with Playwright or an equivalent lightweight tool.
- Add a deterministic demo-data generator for UI screenshots.
- Add `scripts/capture_docs_assets.*` that:
  - starts the local UI in mock/no-model mode,
  - seeds a demo project/video/job if supported,
  - captures README screenshots,
  - creates a small red-ball demo GIF/MP4 if feasible.
- Add docs explaining how to regenerate screenshots.
- Update README to embed the generated assets.

**Acceptance:**

- Screenshots are real, not decorative stock images.
- CI can at least run a smoke version or validate the asset-generation script help.
- README has enough visual proof for a user to understand the tool before installing it.

**Commit:** `phase 03: add docs screenshots and demos`

---

## Phase 03A — Commercial Local UI redesign and layout stabilization

**Goal:** Replace the cluttered, overlapping Local UI with a commercialization-grade product interface that can become the foundation of a paid product.

**Required skills:** `$frontend-design-system`, `$responsive-layout-debugging`, `$visual-regression-testing`, `$accessibility-audit`, `$product-ux-review`. If any are unavailable, Codex must create or locate equivalent skills before implementation.

**Subagents:** `commercial_ui_designer`, `frontend_ui_engineer`, `layout_regression_engineer`, `adoption-scout`, `reviewer`

**Problem statement:** The current Local UI is not acceptable for commercial use if it has cluttered panels, overlapping menus, poor hierarchy, crowded controls, weak visual grouping, unclear project flow, or debug-first screens. Codex must fix this as a product architecture problem, not just a CSS cleanup.

**Tasks:**

- Audit every Local UI screen, route, modal, dropdown, menu, panel, inspector, timeline/job/status area, and provider settings view.
- Capture baseline screenshots at multiple viewport sizes before changing the UI:
  - 1366x768 laptop
  - 1440x900 laptop/desktop
  - 1920x1080 desktop
  - narrow/tablet-like width if supported
- Create `docs/design/local-ui-audit.md` with:
  - screenshots of current issues,
  - overlap/clutter findings,
  - navigation problems,
  - information architecture problems,
  - accessibility problems,
  - priority fixes.
- Create `docs/design/local-ui-product-principles.md` with the commercial UX principles and personas:
  - creator/editor,
  - web developer,
  - ML/CV experimenter,
  - less-technical first-time user,
  - future paid/team user.
- Create `docs/design/design-system.md` covering:
  - layout shell,
  - spacing scale,
  - typography scale,
  - design tokens,
  - z-index rules,
  - navigation patterns,
  - cards/panels/menus/dialogs,
  - status/progress semantics,
  - responsive rules.
- Implement a clean product shell:
  - top app bar with project/context actions,
  - stable side navigation or rail,
  - main workspace,
  - right inspector/settings panel,
  - bottom timeline/job status panel only where useful,
  - global command/help area if practical.
- Rebuild the first-run path as a guided flow:
  1. Create/open project.
  2. Add video.
  3. Choose extraction mode/provider/model.
  4. Confirm credentials/cost/locality.
  5. Run extraction.
  6. Review object candidates.
  7. Correct/refine.
  8. Preview.
  9. Export.
- De-clutter advanced diagnostics behind progressive disclosure:
  - default user view stays simple,
  - advanced/debug panels are available but collapsed or routed separately.
- Fix all overlapping menus/dropdowns/modals/tooltips/panels.
- Standardize z-index, scroll containers, sticky headers, panel sizing, and overflow behavior.
- Add empty/loading/error/offline/no-provider states.
- Add accessible focus behavior for dialogs, menus, and form fields.
- Add visual regression/screenshot tests for core flows.
- Update README/docs screenshots with redesigned UI.

**Likely files/areas:**

- `src/motionjson/local_ui*` or equivalent Local UI serving code
- `src/motionjson/backend*` if API state endpoints are needed
- `packages/*` if the UI runtime is in JS/TS packages
- `docs/local_ui.md`
- `docs/assets/`
- `docs/design/`
- `tests/test_local_ui*`
- `tests/test_*ui*`
- `scripts/capture_docs_assets.*`
- Playwright or browser-test config if present or added

**Tests and validation:**

Codex must discover actual project commands, but expected validation should include where feasible:

```bash
python -m pytest -q
npm run build
npm test
npm run lint
npx playwright test
python -m motionjson.cli ui --no-open --mock
```

Add a viewport overlap check if no visual tool exists. At minimum, create Playwright tests that fail if important menus/dialogs/panels overlap the main workspace incorrectly, become clipped, or create horizontal page overflow at required viewport sizes.

**Acceptance:**

- No menu, dropdown, modal, navigation item, provider panel, inspector, or timeline/status panel overlaps unintentionally at the required viewport sizes.
- The first-run flow is clear without reading docs.
- The UI has an intentional layout system and design tokens.
- Advanced/debug info is accessible without cluttering the default workflow.
- Before/after screenshots are committed or documented with regeneration instructions.
- Visual regression or screenshot smoke tests are present.
- Accessibility basics pass for keyboard navigation and visible focus.
- The phase report includes screenshots, test results, known design compromises, and follow-up items.

**Risk review:**

- Avoid large framework rewrites unless the current stack truly prevents a stable product UI.
- Do not hide provider diagnostics; move them into progressive disclosure.
- Do not introduce paid services, tracking, analytics, or external dependencies without explicit justification.
- Do not hard-code secrets or model choices.

**Commit:** `phase 03a: redesign local ui for commercial readiness`

---

## Phase 03B — BYOK API key and model/provider selection UX

**Goal:** Let users provide their own API keys and choose models/providers from the Local UI while keeping local-first operation, mock/no-model mode, and secret safety intact.

**Required skills:** `$provider-settings-security`, `$frontend-design-system`, `$product-ux-review`, `$accessibility-audit`. If unavailable, Codex must create or locate equivalent skills first.

**Subagents:** `model_provider_architect`, `security_privacy_architect`, `frontend_ui_engineer`, `backend_cv_architect`, `test-gap-scout`, `reviewer`

**Product requirements:**

- Users can choose between local/free providers and hosted/API-backed providers.
- Users can enter their own API key for supported providers.
- Users can select models from a provider-specific list or enter a custom model id when appropriate.
- The UI clearly explains cost, privacy, latency, capability, credential requirements, and whether data leaves the machine.
- No API key should be committed, logged, exposed in screenshots, embedded in generated docs, or sent to the client unnecessarily.

**Provider/model UX:**

The provider settings screen should show provider cards with:

- provider name,
- local vs hosted,
- free/local availability,
- required credentials,
- model selector,
- capability tags: text-guided detection, segmentation, tracking, VLM/object identification, mask generation, refinement, export assistance,
- hardware requirements,
- estimated cost indicator where known,
- privacy warning: whether frames/video are sent off-device,
- readiness status: available, missing dependency, missing key, invalid key, offline, not installed, needs model weights, needs GPU,
- test connection button where safe,
- docs link and troubleshooting link.

**Settings architecture:**

- Define a provider registry schema for model capabilities and credential requirements.
- Add a settings persistence layer that supports:
  - local development defaults,
  - environment-variable override,
  - per-user local config where appropriate,
  - redacted display,
  - deletion/reset.
- Prefer not to store raw keys unless needed. If storing locally is necessary, document the risk and use the safest available local mechanism in the current stack.
- Add `docs/security/api_keys.md` describing:
  - where keys are stored,
  - how to remove keys,
  - what is logged,
  - what is redacted,
  - which providers send video/images off-device,
  - what is safe for demos/Codespaces/Hugging Face Spaces.
- Add `.env.example` entries for supported provider keys without real values.
- Ensure provider diagnostics can read configuration without exposing secrets.

**Model/provider scope:**

Codex must first inspect the current repo for supported provider abstractions. Do not invent unsupported providers as completed features. Start with the providers already present or planned in the repo, such as local/mock, threshold, motion, external masks, YOLO/detectors, SAM2 local/hosted, OpenRouter/VLM, or other current abstractions. If a provider is not implemented, mark it planned in docs/UI rather than pretending it works.

**Likely files/areas:**

- provider registry/capability schema files
- backend settings/config files
- local UI settings screens
- diagnostics endpoints
- `.env.example`
- `docs/providers.md`
- `docs/security/api_keys.md`
- tests for provider settings, secret redaction, diagnostics, and UI forms

**Tests and validation:**

Add tests for:

- API keys are redacted in UI, logs, diagnostics, JSON responses, screenshots, and error messages.
- missing key shows an actionable setup state.
- invalid key shows a safe failure without leaking the key.
- environment variables still work for headless/CLI use.
- model selector options match provider capabilities.
- mock/no-model flow still works with no credentials.
- hosted demo mode disables or clearly walls off credential entry unless safe.

Expected commands where feasible:

```bash
python -m pytest -q
npm run build
npm test
npm run lint
npx playwright test
python -m motionjson.cli backend diagnostics --json
```

**Acceptance:**

- A user can configure a provider key and model choice from the Local UI without touching CLI/env files.
- A CLI/headless user can still use environment variables.
- Secret values are redacted everywhere they appear in UI/API/logs/tests.
- Provider/model capability and cost/privacy information is visible before a user runs extraction.
- Mock/local operation remains the default first-run path.
- Docs clearly distinguish local/free providers from paid/hosted providers.

**Risk review:**

- Do not create a false sense of security. Local key storage must be described honestly.
- Do not send keys to browser/client unless the architecture requires it and the risk is documented. Prefer server-side use.
- Do not enable hosted providers in public demos without a safe credential story.
- Do not log request headers, keys, signed URLs, or provider raw errors containing secrets.

**Commit:** `phase 03b: add provider key and model selection settings`

---

## Phase 04 — Documentation information architecture

**Goal:** Turn the large docs folder into a navigable manual.

**Subagents:** `docs_devrel_engineer`, `product_strategist`, `reviewer`

**Tasks:**

- Rewrite `docs/index.md` as a docs homepage with paths for:
  - “I just want to try it locally.”
  - “I want to extract an object from a video.”
  - “I want to build a website embed.”
  - “I want to develop providers.”
  - “I want to use Codex to contribute.”
- Add `docs/troubleshooting.md`.
- Add `docs/glossary.md` for object layer, mask, track, scene graph, manifest, provider, raster/alpha, vector overlay, and SAM2.
- Add `docs/examples.md` with screenshots and expected output folders.
- Add cross-links from README to these pages.
- Add a docs lint/test that checks important links exist.

**Acceptance:**

- Docs are not just many files; they guide users by intent.
- New terms are explained before they are used heavily.
- Troubleshooting covers missing ffmpeg, CUDA, SAM2, detectors, model weights, bad masks, and raster-only output.

**Commit:** `phase 04: reorganize user documentation`

---

## Phase 05 — CLI and UI first-run quality-of-life

**Goal:** Reduce the chance that users get stuck in CLI copy/paste or silent provider failures.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `qa_benchmark_engineer`, `reviewer`

**Tasks:**

- Add or improve `motionjson doctor` or `motionjson backend diagnostics` presentation for normal users.
- Make local UI landing page show:
  - first-run checklist,
  - available providers,
  - recommended demo path,
  - “start mock demo” button,
  - “run red-ball demo” instructions.
- Improve CLI error messages for missing optional dependencies and unavailable providers.
- Ensure `--mock` mode is explicit and never claims SAM2/detectors are available.
- Add tests for help text and diagnostics output.

**Acceptance:**

- A CPU-only user understands what can run now and what needs optional setup.
- A failed provider path produces actionable diagnostics.
- CLI help and UI diagnostics agree.

**Commit:** `phase 05: improve first-run diagnostics`

---

## Phase 06 — Local/free provider integrations

**Goal:** Strengthen the original product goal: trace one or many objects using multiple local-first strategies.

**Subagents:** `backend_cv_architect`, `qa_benchmark_engineer`, `frontend_ui_engineer`, `reviewer`

**Tasks:**

- Verify current providers: threshold, motion, external masks, SAM2 local/hosted, detector integrations, YOLO, OpenRouter/VLM if present.
- Make provider capability schema clearer: installed, configured, runnable, needs credentials, needs GPU, needs model path, estimated cost.
- Improve local/free providers first:
  - threshold demo provider,
  - motion foreground provider,
  - external mask import,
  - optional YOLO for known classes,
  - optional text detector + SAM2 for text-guided objects.
- Add docs for each provider with “free/local”, “requires GPU?”, “requires model weights?”, “best for”, “failure modes”.
- Add deterministic fixture tests for multi-object extraction and whole-frame-mask rejection.

**Acceptance:**

- Provider choices are understandable in docs and UI.
- Users can choose between semantic/text objects, moving objects, explicit masks, and known detector classes.
- Bad all-frame/raster-only results are detected and explained.

**Commit:** `phase 06: strengthen local provider integrations`

---

## Phase 07 — Object review, correction, and export workflows

**Goal:** Make extraction recoverable instead of one-shot.

**Subagents:** `frontend_ui_engineer`, `backend_cv_architect`, `qa_benchmark_engineer`, `docs_devrel_engineer`, `reviewer`

**Tasks:**

- Improve job review screens for object candidates, tracks, confidence, masks, and failure reasons.
- Add or refine correction flows: relabel, delete, split/merge tracks, repair mask, re-run provider for selected range.
- Document correction workflows with screenshots.
- Add tests for correction APIs and manifest regeneration.
- Ensure exports show what was accepted/rejected.

**Acceptance:**

- A user can inspect and correct a bad extraction before export.
- Docs include a realistic “bad mask to repaired track” walkthrough.

**Commit:** `phase 07: improve review and correction workflows`

---

## Phase 08 — Runtime, SDK, and website embed adoption

**Goal:** Help web developers use the outputs.

**Subagents:** `frontend_ui_engineer`, `release_packaging_engineer`, `docs_devrel_engineer`, `qa_benchmark_engineer`, `reviewer`

**Tasks:**

- Verify `packages/motionjson-runtime` and `packages/motionjson-sdk` build/test paths.
- Add README sections for:
  - plain JS embed,
  - runtime package,
  - SDK usage,
  - output manifest anatomy,
  - website ZIP export,
  - Remotion adapter plan if implemented or planned.
- Add working examples with local demo manifests.
- Add browser smoke tests for embed examples where feasible.

**Acceptance:**

- A frontend developer can use a demo manifest in a webpage without reading the whole codebase.
- SDK/runtime docs are honest about supported formats.

**Commit:** `phase 08: document runtime and SDK adoption`

---

## Phase 09 — CI, packaging, and release readiness

**Goal:** Make the repo safer for Codex and human contributors.

**Subagents:** `release_packaging_engineer`, `qa_benchmark_engineer`, `reviewer`

**Tasks:**

- Add GitHub Actions workflow for Python tests, JS build/lint/tests, docs link checks, and Docker build smoke.
- Add a release checklist:
  - version bump,
  - tests,
  - docs screenshots current,
  - changelog/release notes,
  - package build,
  - Docker build,
  - known limitations.
- Add `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` if missing.
- Add `.gitignore` rules for generated outputs unless intentionally checked in.
- Add repo About/topics recommendations in docs.

**Acceptance:**

- CI catches basic regressions.
- New contributors know how to test and contribute.
- Generated output policy is clear.

**Commit:** `phase 09: add CI and release readiness`

---

## Phase 10 — Free hosted demo surfaces

**Goal:** Provide a no-install or low-install way to try MotionJSON.

**Subagents:** `release_packaging_engineer`, `frontend_ui_engineer`, `docs_devrel_engineer`, `qa_benchmark_engineer`, `reviewer`

**Tasks:**

- Add `.devcontainer/` and Codespaces README badge/instructions.
- Add a Colab notebook for CLI demos:
  - clone repo,
  - install CPU deps,
  - run red-ball demo,
  - inspect output files,
  - avoid long-running public web service hosting.
- Add a Hugging Face Space proof-of-concept plan or minimal app:
  - CPU Basic/mock mode first,
  - small deterministic demo video,
  - no secrets in client,
  - no paid hardware requirement.
- Add deployment warnings around persistence, privacy, and model/provider credentials.

**Acceptance:**

- Codespaces and Colab docs are realistic and current.
- Hosted demo path does not require paid GPU or hidden secrets.
- Limitations are clearly stated.

**Commit:** `phase 10: add free hosted demo paths`

---

## Phase 11 — Advanced product roadmap implementation slices

**Goal:** Continue beyond docs and frontend polish into product depth.

**Subagents:** all relevant agents plus `reviewer`

Implement these as separate subphases with commits:

- **11A Text-guided discovery:** labels -> boxes/candidates -> segmentation/tracking -> review.
- **11B Automatic object proposals:** keyframe masks -> dedupe/filter -> candidate tracks -> user review.
- **11C Motion-only discovery:** frame-difference/background-subtraction/flow -> tracks -> confidence.
- **11D Detector class presets:** YOLO/common classes -> segmentation/tracking -> user-selectable presets.
- **11E Export quality routing:** choose raster alpha, vector silhouette, sprite atlas, transparent WebM, MP4 preview based on quality/resource profile.
- **11F Rights and lineage:** user-visible source asset rights metadata, generated asset lineage, export warnings.
- **11G Asset library:** reusable motion layer packs, brand collections, creator-approved packs if existing backend supports them.
- **11H Commercial workspace mode:** projects, recent files, guided tasks, export presets, user preferences, provider settings, and nontechnical workflows packaged into a cohesive product experience.
- **11I Team/commercial readiness foundation:** account/team boundary placeholders, usage/cost visibility, audit-friendly provider run history, export history, privacy notices, and license/rights reminders without implementing billing unless explicitly requested.

For each subphase:

- keep heavy ML optional;
- add CPU/mock tests;
- add UI/docs screenshots;
- add benchmark fixtures;
- preserve CLI compatibility;
- commit after each subphase.

**Commit examples:**

- `phase 11a: add text-guided discovery workflow`
- `phase 11b: add automatic object proposal workflow`
- `phase 11c: add motion-only discovery workflow`

---

## Phase 12 — Final audit and public launch polish

**Goal:** Make the repo look ready for real users.

**Subagents:** `product_strategist`, `docs_devrel_engineer`, `release_packaging_engineer`, `reviewer`

**Tasks:**

- Re-read README as a first-time user and remove jargon.
- Verify all commands from README/docs actually run or are clearly marked optional/planned.
- Verify screenshots are current.
- Verify release notes and limitations are honest.
- Create a `docs/roadmap/final-audit.md` summarizing completed phases, remaining risks, and next release milestones.
- Recommend GitHub repo settings:
  - description,
  - website/docs URL,
  - topics,
  - pinned demo issue/project,
  - first release tag.

**Acceptance:**

- A new user can understand, install, run, and see what MotionJSON does.
- A contributor can use Codex to continue work without losing phase discipline.
- The project’s public docs do not overclaim beyond current implementation.

**Commit:** `phase 12: complete public launch audit`

---

## README tone guide for Codex

Use a friendly, concrete voice:

- Prefer: “MotionJSON lets you cut a moving object out of a video once, then reuse it as a web-friendly motion layer.”
- Avoid: “This repository implements an extensible segmentation pipeline.”
- Prefer: “Try the no-model demo first. It runs on CPU and does not need SAM2, CUDA, or cloud APIs.”
- Avoid: “Install optional provider dependencies as needed.”

Every major README section should include one of:

- a command a user can run;
- a screenshot;
- a tiny example JSON snippet;
- a demo link/path;
- a limitation or troubleshooting note.

---

## Minimum public README outline

```markdown
# MotionJSON

Turn selected video objects into reusable motion layers for editors and websites.

![Local UI first-run checklist](docs/assets/local-ui-first-run.png)

## What it does
## What it is not
## Who it is for
## 30-second quick start: local UI, no GPU, no cloud
## CLI demo: red ball extraction
## Docker / local API
## Free ways to try it
### GitHub Codespaces
### Google Colab CLI demo
### Hugging Face Space demo plan
## Screenshots and demos
## Output files explained
## Provider options
## Troubleshooting
## Roadmap
## Contributing with Codex
## License
```

---

## Commands Codex should preserve in docs

Local install:

```bash
git clone https://github.com/ptse8204/json-animated-video.git
cd json-animated-video
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e ".[ui]"
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --no-open --mock
```

Red-ball CLI demo:

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo_red_ball \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
python3 -m motionjson.cli validate out/demo_red_ball
```

Local API:

```bash
python3 -m motionjson.cli backend init
python3 -m motionjson.cli backend serve-api \
  --db .motionjson/backend.sqlite \
  --storage-root .motionjson/storage \
  --host 127.0.0.1 \
  --port 8765
```

Docker:

```bash
docker build -t motionjson-ga .
docker run --rm -p 8765:8765 -v motionjson-data:/data motionjson-ga
```

Docker Compose:

```bash
docker compose config
docker compose up --build
```

---

## Final reviewer checklist

Before each commit, reviewer must verify:

- no fake screenshots;
- no unsupported claims;
- README is human-readable;
- local/free run commands are accurate;
- optional ML providers remain optional;
- CPU/mock/no-model smoke path still works;
- Local UI has no obvious layout overlap/clutter regressions at required viewport sizes;
- visual regression or screenshot smoke evidence exists for UI phases;
- API keys/secrets are redacted in UI, logs, diagnostics, tests, screenshots, and docs;
- provider/model selection makes cost, privacy, local/hosted status, and credential requirements clear;
- docs link to limitations and troubleshooting;
- phase report exists;
- relevant tests/smoke commands were run or documented as unavailable.
