# GA Launch Guide

Phase 19 packages the local MotionJSON product surface for general availability
review: deployment artifacts, plan metadata, public docs, onboarding, a landing
page, and a demo gallery.

## Launch Positioning

MotionJSON is for reusable motion layers:

- AI object-layer editing for video and web graphics
- reusable motion layers controlled by JSON
- cached raster/alpha assets for photoreal objects
- SVG and Lottie only for simple vector-like silhouettes, labels, annotations,
  icons, and flat graphics

## GA Readiness Checklist

- Run the local extraction demo and confirm `out/demo/web_asset_manifest.json`
  and `out/demo/scene_graph.json` are generated.
- Start the API with `python -m motionjson.cli backend serve-api`.
- Create a local user, session, project, and hashed API key.
- Confirm `GET /v1/billing/plans` and `GET /v1/billing/status` return local
  catalog metadata only.
- Open `examples/landing_page.html` and `examples/demo_gallery.html` through a
  local static server.
- Review [security_checklist.md](security_checklist.md) before exposing the API
  outside localhost.

## Validation

```bash
pytest -q tests/test_backend_billing.py tests/test_ga_launch_docs.py
pytest -q
npm test
npm run lint
python -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12
git diff --check
```
