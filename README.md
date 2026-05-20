# MotionJSON

Turn selected video objects into reusable motion layers for editors and websites.

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/ptse8204/json-animated-video)

MotionJSON helps you cut a moving object out of a video once, review the result,
and reuse it as a JSON-controlled layer. The practical output is cached
raster/alpha media plus compact JSON for timing, transforms, identity, review
state, rights metadata, and web playback.

Start with the no-model demo. It runs on CPU and does not need SAM2, CUDA,
detectors, model weights, cloud APIs, or provider credentials.

![Local UI first-run checklist](docs/assets/local-ui-first-run.png)

## What it does

- Samples short videos with OpenCV.
- Extracts object layers with local providers such as HSV thresholding, motion
  foreground, external mask imports, and deterministic mock providers.
- Keeps heavyweight ML paths optional and capability-gated.
- Shows provider diagnostics before a run, including missing SAM2, CUDA,
  detectors, hosted endpoints, FFmpeg, and model paths.
- Writes MotionJSON scene files, object manifests, masks, alpha cutouts,
  spritesheets, preview files, rights metadata, fallback diagnostics, and export
  manifests.
- Provides a local UI and local backend surfaces for projects, jobs, review,
  correction, and export.
- Ships JavaScript runtime and SDK packages for using generated assets in web
  pages.

## What it is not

MotionJSON is not a magic "video to JSON/SVG/Lottie" converter. Photoreal video
objects usually contain texture, blur, shadows, hair, reflections, and edge
detail that do not become clean SVG or Lottie. MotionJSON keeps those objects as
raster/alpha assets and controls them with JSON. Vector-like output is best for
silhouettes, contours, labels, icons, annotations, and simple flat graphics.

SAM2 is also not automatic semantic discovery by itself. Text prompts need a
detector or open-vocabulary candidate provider before segmentation/tracking.

## Who it is for

- Creators and editors who want reusable object cutouts from short clips.
- Web developers who want motion layers they can embed without rerunning AI.
- Motion designers who want JSON-controlled timing and transforms over cached
  media.
- Computer-vision experimenters who need visible provider diagnostics and
  CPU/mock test paths.
- Contributors using Codex to continue the local-first object tracing roadmap.

## 30-second quick start: local UI, no GPU, no cloud

After cloning and entering the repository, the one-script path is:

```bash
scripts/first_run_local.sh
```

Manual path:

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

Open the printed local UI URL. In mock mode the UI still reports real
capability status; it does not pretend SAM2, CUDA, detectors, FFmpeg, or model
weights are available.

Windows PowerShell uses the same module command after activating a venv:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[ui]"
python -m motionjson.cli ui --no-open --mock
```

## CLI demo: red ball extraction

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

Expected result: one accepted red-ball object track, sampled frames, masks,
alpha cutouts, MotionJSON files, preview assets, and diagnostics under
`out/demo_red_ball/`.

Optional browser preview:

```bash
python3 -m http.server 8080
```

Then open
`http://localhost:8080/examples/canvas_player.html?scene=/out/demo_red_ball/web_asset_manifest.json`.

## Docker and local API

Run the local backend API without the UI:

```bash
python3 -m motionjson.cli backend init
python3 -m motionjson.cli backend serve-api \
  --db .motionjson/backend.sqlite \
  --storage-root .motionjson/storage \
  --host 127.0.0.1 \
  --port 8765
```

Docker paths are local and use SQLite plus filesystem storage:

```bash
docker build -t motionjson-ga .
docker run --rm -p 8765:8765 -v motionjson-data:/data motionjson-ga
```

```bash
docker compose config
docker compose up --build
```

## Free ways to try it

### GitHub Codespaces

Codespaces should use the CPU/mock path first:

```bash
python3 -m pip install -e ".[ui]"
python3 -m motionjson.cli backend diagnostics --json
python3 -m motionjson.cli ui --no-open --mock --host 0.0.0.0
```

This repository includes `.devcontainer/devcontainer.json` for Codespaces. It
installs Python and Node dependencies after the container starts; then use the
forwarded UI port from the Codespaces Ports panel. The full low-install guide
is [docs/run_free_instances.md](docs/run_free_instances.md).

### Google Colab CLI demo

Colab is useful for short CLI demos, not for hosting a long-running public web
service. The intended path is clone, install CPU dependencies, run the red-ball
demo, and inspect generated files. Use the checked-in
[Colab red-ball CLI notebook](notebooks/colab_red_ball_cli_demo.ipynb).

### Hugging Face Space demo plan

A future Space should start with CPU Basic/mock mode, a tiny deterministic demo
video, no client-side secrets, and no paid GPU requirement. Real SAM2 or
detector demos should stay optional and clearly labeled. The concrete Space
handoff plan lives in [spaces/huggingface/README.md](spaces/huggingface/README.md).

## Screenshots and demos

These images are generated from the local mock UI and the deterministic
red-ball extraction. Regenerate them with:

```bash
python3 scripts/capture_docs_assets.py --check
python3 scripts/capture_docs_assets.py
```

![Local UI project setup](docs/assets/local-ui-new-project.png)

![Goal-first extraction wizard](docs/assets/local-ui-extraction-wizard.png)

![Provider diagnostics](docs/assets/local-ui-provider-diagnostics.png)

![Job review and track status](docs/assets/local-ui-job-review.png)

![Red-ball canvas preview](docs/assets/canvas-preview-red-ball.png)

![Red-ball demo GIF](docs/assets/red-ball-demo.gif)

Available local demo inputs today:

- `examples/demo_red_ball.mp4`
- `examples/make_demo_video.py`
- `examples/canvas_player.html`
- `examples/plain_js_embed.html`
- `examples/object_selection_workflow.html`
- `examples/timeline_editor.html`

## Output files explained

A typical extraction writes files like these:

```text
out/demo_red_ball/
  scene_graph.json
  object_motion.json
  web_asset_manifest.json
  resource_profile.json
  rights_manifest.json
  tracks.json
  fallback_diagnostics.json
  frames/
  masks/
  objects/
  preview/
```

Use `scene_graph.json` or `web_asset_manifest.json` for playback. Use
`tracks.json`, `provider_diagnostics.json`, and `fallback_diagnostics.json` to
understand what was accepted, rejected, or unavailable before export.
Discovered objects also carry a `discovery` block in scene/object/web
manifests. It records candidate source, provider, preset, review status,
selected tracking state, confidence/coverage scores, artifact lineage, and
export review state so runtimes and SDK clients do not need to reverse-engineer
`candidates.json`.
Review APIs also return `review.timeline` with API-owned candidate and track
markers plus suggested keyframes, so the UI scrubber can preview object
appearance/loss and reuse backend-derived keyframes without inventing results.

## Use MotionJSON on a website

Frontend developers can start with the generated `web_asset_manifest.json`
without reading the extraction backend. Serve the repository or an exported
package and open:

```text
http://localhost:8080/examples/plain_js_embed.html?manifest=/out/demo_red_ball/web_asset_manifest.json
```

The plain JavaScript embed uses the local `@motionjson/runtime` source from
`packages/motionjson-runtime`. It auto-mounts elements with
`data-motionjson-src`, renders cached raster/alpha media with JSON timing, and
does not call SAM2, detectors, hosted providers, or model APIs in the browser.

Use `web_asset_manifest.json` for a single object layer. Use
`scene_graph.json` for multi-object playback, layer order, and scene-level edit
state. Both formats reference local cutouts, spritesheets, preview assets,
rights metadata, and production assets when exports create them.

The local package checks are:

```bash
npm test
npm --workspace @motionjson/runtime run test
npm --workspace @motionjson/sdk run test
npm pack --dry-run --workspace @motionjson/runtime
npm pack --dry-run --workspace @motionjson/sdk
npm run embed:smoke
```

Use `@motionjson/sdk` when a web app needs to call the local/backend API:
`MotionJSONClient` can create projects, upload assets, start extractions,
create `website-zip` packages, and request `remotion-plan` render jobs. The SDK
is API orchestration code; website playback still belongs to
`@motionjson/runtime` or the copied `runtime/` folder in a website ZIP.

```bash
python3 -m motionjson.cli export out/demo_red_ball \
  --format website-zip \
  --out out/demo_red_ball/exports/website_package.zip
```

`website-zip` packages the runtime source, HTML previews, snippets, manifests,
cached object media, rights metadata, and production assets for static hosting
or handoff review. Validated UI exports also write `object_layer_pack.json` and
a selected-object website package so downstream users receive only reviewed
object layers plus copyable JavaScript, React, and Remotion handoff snippets.
`remotion-plan` is intentionally honest: it writes a JSON integration plan for
an application-owned Remotion adapter and does not install Remotion or generate
a component today.

## Provider options

| Provider or mode | Local/free? | Best for | Notes |
| --- | --- | --- | --- |
| `mock` | Yes | UI and test smoke checks | Deterministic no-model behavior. |
| `threshold` | Yes | Simple color demos | Good for the red-ball example. |
| `motion` / `motion_foreground` | Yes | Moving objects on simple backgrounds | CPU-friendly, rough by design. |
| `external` / `external_masks` | Yes | Masks from another tool | Import mask PNG/JPG/WebP sequences. |
| `auto_object_proposals` | Mock or optional SAM2 | Clean candidate gallery before selected tracking | Mock mode is no-model; real local proposals require SAM2 automatic masks, torch, checkpoint, and config. |
| `sam2-local` | Optional | Promptable segmentation/tracking | Requires SAM2 package, torch, checkpoint, and config. |
| `sam2-hosted` | Optional | Explicit hosted segmentation experiments | Requires endpoint/auth and opt-in network use. |
| `sam3-local` / `sam3-hosted` | Optional | Concept, exemplar, and higher-recall discovery | Mock modes are no-model; real local SAM3 uses the optional adapter only when Python/CUDA/model diagnostics pass. Hosted SAM3 requires endpoint/auth plus explicit network and cost/privacy acknowledgement. |
| `text_detector` | Optional/scaffolded | Text-guided candidates | Text becomes detector candidates before segmentation. |
| `class_detector` | Optional/scaffolded | Known-class candidates | Requires configured detector model. |
| `openrouter` | Optional | LLM/VLM reasoning or labels | Not a segmentation provider. |

Run this before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --text
python3 -m motionjson.cli backend diagnostics --json
```

Diagnostics now separate `installed`, `configured`, and `runnable`. A provider
can be configured but not runnable, for example hosted segmentation with
credentials present but no explicit network opt-in. The local UI worker starts
`mock`, `threshold`, `motion`, and `external` jobs, plus mock discovery jobs
and configured local SAM2 automatic proposals that feed generated mask handoffs
through the shared review/export path.

The Local UI Provider settings panel lets users bring their own hosted keys and
choose provider models without editing shell files. Raw keys are stored only in
the selected local SQLite database when a user chooses to save them, environment
variables still take precedence for CLI/headless use, and UI/API responses show
only redacted values. See [docs/security/api_keys.md](docs/security/api_keys.md).

## Troubleshooting

The full troubleshooting guide is [docs/troubleshooting.md](docs/troubleshooting.md).
Common first checks:

- `python: command not found`: use `python3` on macOS/Linux or `py -3` on
  Windows.
- SAM2 is missing: use `mock`, `threshold`, `motion`, or `external`, or install
  optional SAM2 dependencies and configure checkpoint/model paths.
- Text/class detectors are missing: install and configure the relevant detector
  only if you need those workflows.
- FFmpeg is missing: JSON and website assets can still work; MP4/WebM rendering
  needs FFmpeg.
- The output is raster-only: inspect `fallback_diagnostics.json` and
  `tracks.json`. Photoreal objects are expected to remain raster/alpha, but bad
  whole-frame masks should be flagged before export.
- The UI cannot find a video path: the local backend only registers files it
  can read from the machine running the server.

More docs:

- [Docs index](docs/index.md)
- [First run setup](docs/first_run.md)
- [Run locally](docs/run_local.md)
- [Run on free instances](docs/run_free_instances.md)
- [Examples](docs/examples.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Glossary](docs/glossary.md)
- [Local UI](docs/local_ui.md)
- [Provider capabilities](docs/provider_capabilities.md)
- [Provider API keys](docs/security/api_keys.md)
- [Discovery providers](docs/discovery_providers.md)
- [Track filtering](docs/track_filtering.md)
- [Runtime guide](docs/runtime.md)
- [Release checklist](docs/release_checklist.md)
- [Migration and known limitations](docs/migration_and_known_limitations.md)
- [Deployment guide](docs/deployment.md)
- [Repository status](docs/repo_status.md)

## Roadmap

The current public-onboarding roadmap is in `docs/codex_future_plan.md`.
Completed implementation history from the earlier roadmap is recorded under
`docs/roadmap/`. The latest launch-readiness summary is
[`docs/roadmap/final-audit.md`](docs/roadmap/final-audit.md).

Current release-candidate boundaries:

- the no-model local UI, red-ball CLI demo, benchmark fixtures, docs links,
  JavaScript runtime checks, and local API tests are covered by repeatable
  commands;
- SAM2, detector, hosted segmentation, OpenRouter, FFmpeg video rendering, and
  public hosted demos remain optional or environment-dependent;
- no license file is present in this repository snapshot, so reuse,
  redistribution, and commercial rights are not granted yet.

## Contributing with Codex

Read `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, `codex_tasks.yaml`, and
`docs/codex_future_plan.md` before making roadmap changes. Work phase by phase,
run the relevant smoke commands, write a phase report, and commit each phase.

Contributor, release, and security docs:

- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)
- [Release checklist](docs/release_checklist.md)

The old root README planning packet was preserved at
`docs/codex/planning_packet.md` so Codex instructions are not lost.

## License

No license file is present in this repository snapshot. Do not assume reuse,
redistribution, or commercial rights until the project adds an explicit license.
