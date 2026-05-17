# README Assets

This file tracks the real assets the public README should eventually embed.
Do not add fake screenshots or decorative placeholder images. If an asset is
not captured yet, keep it listed here as pending.

## Required Assets

| Asset | Status | How to regenerate |
| --- | --- | --- |
| `docs/assets/local-ui-first-run.png` | Pending | Phase 03 should start `python3 -m motionjson.cli ui --no-open --mock`, open the local UI, and capture the first-run checklist. |
| `docs/assets/local-ui-new-project.png` | Pending | Phase 03 should seed or create a local project in mock mode and capture the project panel. |
| `docs/assets/local-ui-extraction-wizard.png` | Pending | Phase 03 should select a demo video and capture the goal-first extraction wizard. |
| `docs/assets/local-ui-provider-diagnostics.png` | Pending | Phase 03 should capture capability diagnostics showing ready no-model providers and unavailable optional ML providers. |
| `docs/assets/local-ui-job-review.png` | Pending | Phase 03 should run or seed a mock job and capture object tracks, confidence, warnings, and export status. |
| `docs/assets/canvas-preview-red-ball.png` | Pending | Phase 03 should run the red-ball demo and capture a real preview frame or canvas playback view. |
| `docs/assets/red-ball-demo.gif` | Optional pending | Phase 03 may create a small GIF if size and quality are acceptable. |
| `docs/assets/red-ball-demo.mp4` | Optional pending | Phase 03 may create a short MP4 if it is more efficient than GIF. |

## Current Manual Demo Commands

Use these until screenshot automation exists:

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
python3 -m motionjson.cli ui --no-open --mock
```

## Acceptance Notes

- Screenshots must come from the local app or generated demo output.
- Images should show actual MotionJSON UI state, not stock imagery.
- If provider failures are visible, they should be real diagnostics from
  `backend diagnostics --json` or `/api/capabilities`.
- Do not commit large generated videos unless the phase report justifies the
  size and regeneration path.
