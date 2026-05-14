# Onboarding Guide

This guide gets a new local operator from a demo clip to a reusable motion
layer, API key, and website preview.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 2. Generate Demo Assets

```bash
python examples/make_demo_video.py --out examples/demo_red_ball.mp4
python -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
```

## 3. Preview

```bash
python -m http.server 8080
```

Open:

- `http://localhost:8080/examples/landing_page.html`
- `http://localhost:8080/examples/demo_gallery.html`
- `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/timeline_editor.html?scene=/out/demo/scene_graph.json`

## 4. Local API

```bash
python -m motionjson.cli backend init
printf '%s' "$MOTIONJSON_PASSWORD" | python -m motionjson.cli backend create-user --email user@example.com --password-stdin
export MOTIONJSON_SESSION_TOKEN="$(
  printf '%s' "$MOTIONJSON_PASSWORD" | python -m motionjson.cli backend login --email user@example.com --password-stdin | python -c 'import json,sys; print(json.load(sys.stdin)["sessionToken"])'
)"
python -m motionjson.cli backend create-api-key --name "local sdk"
python -m motionjson.cli backend list-plans
python -m motionjson.cli backend billing-status
python -m motionjson.cli backend serve-api
```

## 5. Validate

```bash
pytest -q
npm test
npm run lint
git diff --check
```
