# Onboarding Guide

This guide gets a new local operator from a demo clip to a reusable motion
layer, API key, and website preview. For install profiles, Windows PowerShell
commands, first-run diagnostics, and multi-object tutorial commands, start with
[First run setup](first_run.md).

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -m pip install -e ".[ui]"
```

## 2. Generate Demo Assets

```bash
python3 examples/make_demo_video.py --out examples/demo_red_ball.mp4
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 \
  --out out/demo \
  --mask-provider threshold \
  --lower-hsv 0,80,80 \
  --upper-hsv 12,255,255 \
  --sample-fps 12 \
  --max-frames 12
```

## 3. Preview

```bash
python3 -m http.server 8080
```

Open:

- `http://localhost:8080/examples/landing_page.html`
- `http://localhost:8080/examples/demo_gallery.html`
- `http://localhost:8080/examples/canvas_player.html?scene=/out/demo/web_asset_manifest.json`
- `http://localhost:8080/examples/timeline_editor.html?scene=/out/demo/scene_graph.json`

## 4. Guided Local UI

```bash
python3 -m motionjson.cli ui --no-open --mock
```

Open the printed local URL. The default workspace is step-by-step:

1. Choose goal.
2. Create/open project.
3. Add/select video.
4. Choose mode/provider.
5. Add prompts/keyframes.
6. Validate and run.
7. Review candidates/tracks.
8. Correct tracks.
9. Preview/export.

Use `Start mock job` for a no-model smoke run. The left menu and right details
rail are collapsible; provider failures, failed runs, and fallback diagnostics
remain visible when they need attention. `Show all panels` restores the
advanced dashboard view for debugging.

## 5. Local API

```bash
python3 -m motionjson.cli backend init
printf '%s' "$MOTIONJSON_PASSWORD" | python3 -m motionjson.cli backend create-user --email user@example.com --password-stdin
export MOTIONJSON_SESSION_TOKEN="$(
  printf '%s' "$MOTIONJSON_PASSWORD" | python3 -m motionjson.cli backend login --email user@example.com --password-stdin | python3 -c 'import json,sys; print(json.load(sys.stdin)["sessionToken"])'
)"
python3 -m motionjson.cli backend create-api-key --name "local sdk"
python3 -m motionjson.cli backend list-plans
python3 -m motionjson.cli backend billing-status
python3 -m motionjson.cli backend serve-api
```

## 6. Validate

```bash
pytest -q
npm test
npm run lint
git diff --check
```
