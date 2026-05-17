# MotionJSON

Turn selected video objects into reusable motion layers for editors and websites.

MotionJSON helps you cut a moving object out of a video once, review the result,
and reuse it as a JSON-controlled layer. The practical output is cached
raster/alpha media plus compact JSON for timing, transforms, identity, review
state, rights metadata, and web playback.

Start with the no-model demo. It runs on CPU and does not need SAM2, CUDA,
detectors, model weights, cloud APIs, or provider credentials.

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

A devcontainer is planned in the first-run phase. Until then, install Python
dependencies in the Codespaces terminal and use forwarded ports.

### Google Colab CLI demo

Colab is useful for short CLI demos, not for hosting a long-running public web
service. The intended path is clone, install CPU dependencies, run the red-ball
demo, and inspect generated files. A notebook is planned for the hosted-demo
phase.

### Hugging Face Space demo plan

A future Space should start with CPU Basic/mock mode, a tiny deterministic demo
video, no client-side secrets, and no paid GPU requirement. Real SAM2 or
detector demos should stay optional and clearly labeled.

## Screenshots and demos

Screenshot automation is not ready yet, so this README does not embed fake or
placeholder PNGs. The required README assets and regeneration plan live in
`docs/assets/README_ASSETS.md`.

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

## Provider options

| Provider or mode | Local/free? | Best for | Notes |
| --- | --- | --- | --- |
| `mock` | Yes | UI and test smoke checks | Deterministic no-model behavior. |
| `threshold` | Yes | Simple color demos | Good for the red-ball example. |
| `motion` / `motion_foreground` | Yes | Moving objects on simple backgrounds | CPU-friendly, rough by design. |
| `external` / `external_masks` | Yes | Masks from another tool | Import mask PNG/JPG/WebP sequences. |
| `sam2-local` | Optional | Promptable segmentation/tracking | Requires SAM2 package, torch, checkpoint, and config. |
| `sam2-hosted` | Optional | Explicit hosted segmentation experiments | Requires endpoint/auth and opt-in network use. |
| `text_detector` | Optional/scaffolded | Text-guided candidates | Text becomes detector candidates before segmentation. |
| `class_detector` | Optional/scaffolded | Known-class candidates | Requires configured detector model. |
| `openrouter` | Optional | LLM/VLM reasoning or labels | Not a segmentation provider. |

Run this before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

## Troubleshooting

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
- [Local UI](docs/local_ui.md)
- [Provider capabilities](docs/provider_capabilities.md)
- [Discovery providers](docs/discovery_providers.md)
- [Track filtering](docs/track_filtering.md)
- [Runtime guide](docs/runtime.md)
- [Migration and known limitations](docs/migration_and_known_limitations.md)
- [Deployment guide](docs/deployment.md)
- [Repository status](docs/repo_status.md)

## Roadmap

The current public-onboarding roadmap is in `docs/codex_future_plan.md`.
Completed implementation history from the earlier roadmap is recorded under
`docs/roadmap/`. Near-term public polish work focuses on:

- real README screenshots and demo capture;
- first-run scripts for local and free-instance paths;
- a clearer docs information architecture;
- generated output policy and CI checks;
- provider docs that explain local/free, GPU, model, and failure-mode tradeoffs.

## Contributing with Codex

Read `AGENTS.md`, `CODEX_MASTER_PROMPT.md`, `codex_tasks.yaml`, and
`docs/codex_future_plan.md` before making roadmap changes. Work phase by phase,
run the relevant smoke commands, write a phase report, and commit each phase.

The old root README planning packet was preserved at
`docs/codex/planning_packet.md` so Codex instructions are not lost.

## License

No license file is present in this repository snapshot. Do not assume reuse,
redistribution, or commercial rights until the project adds an explicit license.
