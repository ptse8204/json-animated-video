# Run MotionJSON Locally

Use this guide when you want a copy-paste local setup. The default UI path is
real-provider-first: connect local SAM2/SAM3 or a hosted SAM profile in Model
Connections, then validate before extraction. Debug mock mode is reserved for
contributor smoke checks.

## One-script UI setup

From the repository root:

```bash
scripts/first_run_local.sh
```

The script creates `.venv`, installs the local package with the `ui` extra, runs
provider diagnostics, and starts the local UI.

For CI or documentation checks where a blocking server is not useful:

```bash
scripts/first_run_local.sh --no-launch
```

PowerShell:

```powershell
.\scripts\first_run_local.ps1
```

## Prerequisites

- Python `>=3.10`.
- Git for cloning the repository.
- 4 GB RAM minimum for tiny CPU/no-model demos; 8 GB recommended. See
  [System requirements](system_requirements.md) before configuring SAM2/SAM3.
- Optional: Docker and Docker Compose for API container checks.
- Optional: Node.js for `npm run build`, `npm test`, and `npm run lint`.
- Optional: FFmpeg for MP4/WebM exports. JSON/runtime outputs still work
  without FFmpeg.

## Manual UI setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -U pip
python3 -m pip install -e ".[ui]"
python3 -m motionjson.cli ui --no-open
```

Run diagnostics before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

Missing optional providers should be shown as diagnostics, not treated as base
install failures.

## Contributor Debug UI

```bash
python3 -m motionjson.cli ui --no-open --debug-mock
```

The legacy `scripts/run_local_ui_mock.sh` helper remains for layout/tests. Use
it only when you specifically need the deterministic debug no-model UI. Useful
overrides:

```bash
scripts/run_local_ui_mock.sh \
  --db /tmp/motionjson-local/backend.sqlite \
  --storage-root /tmp/motionjson-local/storage \
  --host 127.0.0.1 \
  --port 8766
```

The UI command is blocking. Stop it with `Ctrl-C`.

## Red-ball CLI demo

```bash
scripts/run_red_ball_demo.sh
```

Equivalent manual commands:

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

Optional browser preview:

```bash
python3 -m http.server 8080
```

Open:

```text
http://localhost:8080/examples/canvas_player.html?scene=/out/demo_red_ball/web_asset_manifest.json
```

## Local backend API

Start the dependency-light local API:

```bash
scripts/run_backend_api.sh
```

Equivalent manual commands:

```bash
python3 -m motionjson.cli backend init
python3 -m motionjson.cli backend serve-api \
  --db .motionjson/backend.sqlite \
  --storage-root .motionjson/storage \
  --host 127.0.0.1 \
  --port 8765
```

For setup checks that should not block:

```bash
scripts/run_backend_api.sh --init-only
```

Most backend API routes require local auth. Use the backend CLI to create a
user, log in, and mint an API key before calling protected routes from another
client. See [Developer API](developer_api.md) for the full API workflow.

## Docker

The Docker image starts the backend API, not the full local UI:

```bash
docker build -t motionjson-ga .
docker run --rm -p 8765:8765 -v motionjson-data:/data motionjson-ga
```

## Docker Compose

```bash
docker compose config
docker compose up --build
```

Compose persists `/data/backend.sqlite` and `/data/storage` in the
`motionjson-data` volume.

## Optional ML providers

Keep the default install CPU-friendly. Add optional extras only when you are
ready to configure the provider:

```bash
python3 -m pip install -e ".[sam2]"
python3 -m pip install -e ".[sam2-transformers]"
python3 -m pip install -e ".[sam3-transformers]"
python3 -m pip install -e ".[sam3]"
python3 -m pip install -e ".[detectors]"
python3 -m pip install -e ".[yolo]"
python3 -m pip install -e ".[hosted-segmentation]"
python3 -m pip install -e ".[hosted-sam3]"
python3 -m pip install -e ".[openrouter]"
```

The `sam3-transformers` extra is the normal local SAM3 Scene Sweep path. It
uses `sam3TrackerModel=facebook/sam3` by default, or a local Hugging Face
`from_pretrained` directory, and it does not require SAM2. The `sam3` extra is
for Advanced official-package concept/exemplar diagnostics and adapter code.
That path still requires the official SAM3 package installed separately,
Python 3.12+, CUDA-capable torch, model access, and a configured
`SAM3_LOCAL_MODEL`/`sam3ModelPath`. A saved model path or provider setting is
not enough by itself; diagnostics must report the provider as runnable before a
real SAM3 job should be started.

Then rerun:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

Diagnostics should explain missing model paths, credentials, CUDA, FFmpeg, or
provider packages before a run starts.

## Cleanup

Generated local files are safe to remove when you are done experimenting:

```bash
rm -rf .motionjson out/demo_red_ball out/benchmarks
```

Do not remove generated outputs that you intentionally want to keep as demos or
fixtures.
