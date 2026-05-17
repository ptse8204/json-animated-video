# README Assets

This file tracks the real assets embedded by the public README. Do not add fake
screenshots or decorative placeholder images. If an asset is not captured yet,
keep it listed here as pending.

## Required Assets

| Asset | Status | How to regenerate |
| --- | --- | --- |
| `docs/assets/local-ui-first-run.png` | Generated | `python3 scripts/capture_docs_assets.py` starts the local UI in mock mode and captures the first-run checklist. |
| `docs/assets/local-ui-new-project.png` | Generated | `python3 scripts/capture_docs_assets.py` seeds a demo project/video and captures the project setup panel. |
| `docs/assets/local-ui-extraction-wizard.png` | Generated | `python3 scripts/capture_docs_assets.py` captures the goal-first extraction wizard with the text-detector preset selected. |
| `docs/assets/local-ui-provider-diagnostics.png` | Generated | `python3 scripts/capture_docs_assets.py` captures capability diagnostics from `/api/capabilities`. |
| `docs/assets/local-ui-job-review.png` | Generated | `python3 scripts/capture_docs_assets.py` runs a mock job and captures the job review surface. Regenerate after UI layout changes when docs need the latest Track Detail and correction panels. |
| `docs/assets/canvas-preview-red-ball.png` | Generated | `python3 scripts/capture_docs_assets.py` runs the threshold red-ball extraction and overlays the real mask on a sampled frame. |
| `docs/assets/red-ball-demo.gif` | Generated | `python3 scripts/capture_docs_assets.py` creates a small GIF from generated red-ball frames and masks. |
| `docs/assets/red-ball-demo.mp4` | Not generated | The GIF is the current lightweight README demo; generate MP4 only if later docs need lower file size or better playback quality. |

## Regenerate Assets

Check whether Chrome/Chromium is available for UI screenshots:

```bash
python3 scripts/capture_docs_assets.py --check
```

Capture every README asset:

```bash
python3 scripts/capture_docs_assets.py
```

Generate only the red-ball preview and GIF, without browser screenshots:

```bash
python3 scripts/capture_docs_assets.py --skip-browser
```

The full capture path uses temporary SQLite/storage directories, starts
`python3 -m motionjson.cli ui --no-open --mock`, seeds a demo project through
the real local API, runs a deterministic mock job, and captures screenshots with
headless Chrome/Chromium. It does not require SAM2, CUDA, detectors, model
weights, cloud APIs, or provider credentials.

## Manual Demo Commands

Use these when debugging the underlying red-ball extraction:

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
