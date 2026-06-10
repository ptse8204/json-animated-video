# MotionJSON / json-animated-video — Codex Future Plan

This file is written as a Codex-processable implementation brief. It is intended to be copied into the repository root or into `docs/codex_future_plan.md`, then used with Codex from the repo root.

Repository: `https://github.com/ptse8204/json-animated-video`

---

## Codex Goal

Use this as the active Codex Goal:

```text
/goal Turn MotionJSON into a human-onboardable, local-first video object-layer editing project, verified by a rewritten public README, local/free run paths, screenshots/demos, CI-safe smoke tests, and phase reports for every completed phase, while preserving CLI compatibility, optional heavy ML dependencies, CPU/mock/no-model operation, and clear provider diagnostics. Use the repo, existing AGENTS.md/CODEX_MASTER_PROMPT.md/codex_tasks.yaml/docs, and local test outputs as evidence. Continue phase by phase until all phases below are complete; if a phase is blocked, commit the completed safe slice, write the blocker and unlock condition in the phase report, and continue only when the blocker is resolved.
```

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
- `backend_cv_architect`: improve provider capability checks, local/free providers, segmentation/tracking pipeline, exports, and diagnostics.
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
- docs link to limitations and troubleshooting;
- phase report exists;
- relevant tests/smoke commands were run or documented as unavailable.
