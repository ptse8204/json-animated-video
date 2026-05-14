# SaaS Backend

Phase 12 adds a local, framework-independent backend foundation for MotionJSON.
It stores metadata in SQLite and stores bytes through the `StorageProvider`
protocol, with `LocalStorageProvider` as the default implementation.

The backend manages users, sessions, projects, assets, jobs, queue items,
workers, usage events, rights metadata, asset lineage, and audit events. It
does not add an HTTP server, billing, webhooks, marketplace features, public API
keys, SDKs, admin tools, or broad legal-advice workflows.

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
python -m motionjson.cli backend asset-rights ASSET_ID --session-token-env MOTIONJSON_SESSION_TOKEN
```

`--db` and `--storage-root` can be passed to every backend command. Defaults
come from `MOTIONJSON_BACKEND_DB` and `MOTIONJSON_STORAGE_ROOT`, falling back to
`.motionjson/backend.sqlite` and `.motionjson/storage`.

Upload and extraction commands accept local rights metadata flags such as
`--rights-display-text`, `--license`, `--license-name`, `--creator-approved`,
and `--commercial-use`. These flags only persist structured metadata; they do
not call external services or establish legal clearance.

## Rights, Lineage, and Audit

Phase 13 adds three local SQLite tables:

- `rights_metadata`: rights JSON per asset/object plus creator approval and
  commercial-use fields.
- `asset_lineage`: source asset to derived asset edges with job id, operation,
  object id, and metadata.
- `audit_events`: user, project, job, asset, and object scoped local audit
  records.

Uploads record initial source rights. Extraction records lineage from uploaded
source video to generated manifests, cutouts, masks, and package-ready JSON.
Website package export records package lineage and preserves the extraction
`rights_manifest.json`. See `docs/rights_and_lineage.md`.

## Validation

```bash
pytest -q
npm test
npm run lint
git diff --check
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson_phase13_demo --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12
```
