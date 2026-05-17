---
title: MotionJSON CPU Mock Demo
sdk: docker
app_port: 8766
pinned: false
---

# Hugging Face Space Proof-Of-Concept Plan

This is a plan for a safe first MotionJSON Space. It is intentionally CPU-only
and mock-first. Do not add provider credentials, paid GPU assumptions, private
videos, or automatic model downloads to a public demo.

## Target Hardware

- Use CPU Basic first.
- Treat persistent storage as optional. Default Space storage may be reset.
- Keep the demo video tiny and deterministic: `examples/demo_red_ball.mp4`, or
  generate it at startup with `examples/make_demo_video.py`.

## Startup Command

Use the existing local UI in mock mode:

```bash
python -m motionjson.cli backend diagnostics --json
python -m motionjson.cli ui --no-open --mock --host 0.0.0.0 --port 8766
```

The diagnostics output must remain visible in logs so unavailable SAM2,
detectors, FFmpeg, model weights, hosted segmentation, or provider credentials
are clear before a user runs anything.

## Data And Secret Rules

- Do not put API keys, hosted segmentation credentials, OpenRouter keys, or
  model license tokens in client-side code.
- Use Hugging Face Space secrets only for an explicitly labeled optional
  provider demo.
- Keep uploaded videos and generated outputs inside the Space runtime storage.
- Do not promise persistence unless a persistent storage tier is configured and
  documented.

## Minimal Docker Space Shape

The repository `Dockerfile` already starts the backend API. A Space-specific
Dockerfile can instead install the package and run the local UI on port 8766:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY . .
RUN python -m pip install --no-cache-dir -e ".[ui]"
EXPOSE 8766
CMD ["python", "-m", "motionjson.cli", "ui", "--no-open", "--mock", "--host", "0.0.0.0", "--port", "8766"]
```

## Launch Checklist

- Confirm CPU Basic launches without SAM2, detectors, hosted endpoints, or paid
  GPU hardware.
- Confirm the UI shows provider diagnostics and a mock/no-model path.
- Confirm example media is tiny and generated or bundled intentionally.
- Confirm logs and public responses do not expose local absolute paths, storage
  keys, API keys, or provider credentials.
- Label real SAM2, detector, or hosted-provider demos as optional and
  credentialed before enabling them.
