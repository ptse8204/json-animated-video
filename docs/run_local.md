# Run MotionJSON Locally

Use this guide when you want a copy-paste local setup. The default path is
CPU/mock/no-model and does not require SAM2, CUDA, hosted services, detector
weights, or cloud API keys.

## One-script UI setup

From the repository root:

```bash
scripts/first_run_local.sh
```

The script creates `.venv`, installs the local package with the `ui` extra, runs
provider diagnostics, and starts the local UI in mock mode.

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
python3 -m motionjson.cli ui --no-open --mock
```

Run diagnostics before choosing a provider:

```bash
python3 -m motionjson.cli backend diagnostics --json
```

Missing optional providers should be shown as diagnostics, not treated as base
install failures.

## Start the mock UI again

```bash
scripts/run_local_ui_mock.sh
```

Useful overrides:

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
python3 -m pip install -e ".[detectors]"
python3 -m pip install -e ".[yolo]"
python3 -m pip install -e ".[hosted-segmentation]"
python3 -m pip install -e ".[openrouter]"
```

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
