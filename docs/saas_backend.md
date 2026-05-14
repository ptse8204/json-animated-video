# SaaS Backend

Phase 12 adds a local, framework-independent backend foundation for MotionJSON.
It stores metadata in SQLite and stores bytes through the `StorageProvider`
protocol, with `LocalStorageProvider` as the default implementation.

The backend manages users, sessions, projects, assets, jobs, queue items,
workers, and usage events. It does not add an HTTP server, billing, webhooks,
marketplace features, public API keys, SDKs, admin tools, or rights/lineage
features.

## Product Boundary

MotionJSON turns useful video elements into reusable motion layers for editors
and websites. The backend preserves the core architecture:

- AI or segmentation work happens at ingest, correction, labeling, or
  optimization time.
- Normal edit preview uses cached raster/alpha assets and JSON transforms.
- Photoreal objects stay raster/alpha by default.
- SVG/Lottie is reserved for simple vector-like silhouettes, labels,
  annotations, icons, and flat graphics.

## Provider Policy

Backend extraction defaults to deterministic local providers. Accepted
segmentation payload values are:

- `threshold`
- `external`
- `mock`

OpenRouter-style LLM/VLM routing remains reasoning-only and is explicitly not
accepted as a pixel segmentation provider. Hosted/SAM2/network providers remain
separate opt-in integration points and are not used by backend tests.

## CLI

```bash
python -m motionjson.cli backend init --db .motionjson/backend.sqlite --storage-root .motionjson/storage
python -m motionjson.cli backend create-user --email user@example.com --password-stdin
python -m motionjson.cli backend login --email user@example.com --password-stdin
python -m motionjson.cli backend create-project --session-token-env MOTIONJSON_SESSION_TOKEN --name "Demo"
python -m motionjson.cli backend upload-asset --project-id PROJECT_ID --path examples/demo_red_ball.mp4 --kind source_video
python -m motionjson.cli backend enqueue-extract --project-id PROJECT_ID --asset-id ASSET_ID --mask-provider threshold --max-frames 12
python -m motionjson.cli backend enqueue-export --project-id PROJECT_ID --source-job-id JOB_ID --format website-zip
python -m motionjson.cli backend worker --once
python -m motionjson.cli backend job-status JOB_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend usage --project-id PROJECT_ID --session-token-env MOTIONJSON_SESSION_TOKEN
```

`--db` and `--storage-root` can be passed to every backend command. Defaults
come from `MOTIONJSON_BACKEND_DB` and `MOTIONJSON_STORAGE_ROOT`, falling back to
`.motionjson/backend.sqlite` and `.motionjson/storage`.

## Validation

```bash
pytest -q
npm test
npm run lint
git diff --check
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson_phase12_demo --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12
```
