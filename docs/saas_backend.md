# SaaS Backend

Phase 12 adds a local, framework-independent backend foundation for MotionJSON.
It stores metadata in SQLite and stores bytes through the `StorageProvider`
protocol, with `LocalStorageProvider` as the default implementation.

The backend manages users, sessions, API keys, projects, assets, jobs, queue
items, workers, usage events, rights metadata, asset lineage, audit events, and
local webhook records. Phase 17 adds closed beta invite/member records,
project-scoped feedback, redacted error reports, and an admin dashboard. Phase
18 adds a local marketplace foundation: saved reusable library assets, brand
collections, tags/search/license filters, and creator-approved packs. Phase 19
adds a local billing/pricing catalog and entitlement status slice. Payment
collection, public marketplace commerce, and broad legal-advice workflows remain
out of scope.

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

## Diagnostics

Provider diagnostics are available without initializing the backend database or
storage root:

```bash
python -m motionjson.cli backend diagnostics --json
```

Use `--video` and `--output-dir` to probe a planned source video and output
location. Diagnostics are advisory preflight data for UI and CLI workflows; they
do not change backend provider policy, start jobs, make hosted network calls, or
print secret values.

## Usage, Latency, And Cost Dashboard

Phase 16 records extraction performance data without changing provider policy.
Backend extraction jobs persist:

- `latency_ms` usage events and a `latency_metrics` job event
- provider attempt usage events derived from the extraction cost dashboard
- cache hit and miss usage events with byte metadata
- a `cost_dashboard` job event that reports local zero-cost providers or
  explicit unknown hosted/custom provider costs

`python -m motionjson.cli backend usage` returns `costDashboard` alongside raw
events and totals. The dashboard is advisory accounting over recorded
usage/provider/cache/latency data. It does not make paid API calls and does not
store secrets.

## CLI

```bash
python -m motionjson.cli backend init --db .motionjson/backend.sqlite --storage-root .motionjson/storage
python -m motionjson.cli backend diagnostics --json
python -m motionjson.cli backend create-user --email user@example.com --password-stdin
python -m motionjson.cli backend login --email user@example.com --password-stdin
python -m motionjson.cli backend create-project --session-token-env MOTIONJSON_SESSION_TOKEN --name "Demo"
python -m motionjson.cli backend upload-asset --project-id PROJECT_ID --path examples/demo_red_ball.mp4 --kind source_video
python -m motionjson.cli backend enqueue-extract --project-id PROJECT_ID --asset-id ASSET_ID --mask-provider threshold --max-frames 12
python -m motionjson.cli backend enqueue-export --project-id PROJECT_ID --source-job-id JOB_ID --format website-zip
python -m motionjson.cli backend worker --once
python -m motionjson.cli backend create-api-key --session-token-env MOTIONJSON_SESSION_TOKEN --name "local sdk"
python -m motionjson.cli backend serve-api --host 127.0.0.1 --port 8765
python -m motionjson.cli backend job-status JOB_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend cancel-job JOB_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend usage --project-id PROJECT_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend asset-rights ASSET_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend save-library-asset --project-id PROJECT_ID --asset-id ASSET_ID --type motion_sticker --title "Launch sticker" --tag hero --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend list-library-assets --tag hero --creator-approved true --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend create-brand-collection --project-id PROJECT_ID --title "Spring launch" --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend add-collection-asset --collection-id COLLECTION_ID --library-asset-id LIBRARY_ASSET_ID --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend create-creator-pack --collection-id COLLECTION_ID --title "Approved launch pack" --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend bootstrap-beta-admin --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend create-beta-invite --email beta-user@example.com --role member --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend accept-beta-invite --invite-token mjb_... --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend feedback --project-id PROJECT_ID --subject "Beta issue" --message "Layer jumps" --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend error-report --project-id PROJECT_ID --message "Render failed" --stack-trace "$STACK_TRACE" --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend admin-dashboard --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend list-plans
python -m motionjson.cli backend billing-status --session-token-env MOTIONJSON_SESSION_TOKEN
```

`--db` and `--storage-root` can be passed to every backend command. Defaults
come from `MOTIONJSON_BACKEND_DB` and `MOTIONJSON_STORAGE_ROOT`, falling back to
`.motionjson/backend.sqlite` and `.motionjson/storage`.

Upload and extraction commands accept local rights metadata flags such as
`--rights-display-text`, `--license`, `--license-name`, `--creator-approved`,
and `--commercial-use`. These flags only persist structured metadata; they do
not call external services or establish legal clearance.

Asset-library commands only reference existing backend asset rows and rights
metadata. They do not copy stored bytes, do not call AI providers, and report
`aiUsage: none` for normal save/search/list/collection/pack operations.
Creator-approved packs reject collection assets unless rights metadata marks
creator approval and commercial use as approved. See
`docs/asset_library_marketplace.md`.

## Closed Beta And Support

Closed beta access uses `beta_invites` and `beta_members`. Invite tokens are
printed once, stored only as SHA-256 hashes, and can be accepted once before
expiry unless revoked. Admin commands and admin API routes require an explicit
`beta_members.role = admin`; ordinary beta members receive 403 responses.

Feedback and error reports are authenticated and can be scoped to projects and
jobs. The backend redacts obvious bearer tokens, API-key-like values, URL query
strings, sensitive metadata keys, storage keys, and oversized context before
storage. Admin listing and dashboard responses avoid raw invite tokens, token
hashes, API-key hashes, webhook secrets, storage keys, and uploaded bytes.

See `docs/beta_readiness.md`, `docs/support.md`, and `docs/privacy.md`.

## Developer API

Phase 15 adds a stdlib HTTP server under `motionjson.backend.api`. It validates
bearer API keys, stores only API-key hashes, and exposes local endpoints for
project create/list/get, asset upload/list/get/download, extraction enqueue, job
status/events, website asset-package enqueue, cached-asset render enqueue, and
webhook management/delivery listing.
Phase 17 adds `GET /v1/beta/status`, `POST /v1/beta/accept`,
`POST /v1/feedback`, `POST /v1/error-reports`, admin beta invite/member routes,
admin feedback/error listing, and `GET /v1/admin/dashboard`.
Phase 18 adds `POST /v1/projects/{projectId}/library-assets`,
`GET /v1/library/assets`, `GET /v1/library/assets/{libraryAssetId}`,
`POST /v1/library/collections`, `GET /v1/library/collections`,
`POST /v1/library/collections/{collectionId}/assets`,
`GET /v1/library/collections/{collectionId}/assets`,
`POST /v1/library/packs`, and `GET /v1/library/packs`. Phase 19 adds
`GET /v1/billing/plans` and `GET /v1/billing/status`.

Billing routes expose local plan catalog and entitlement metadata only. They do
not create checkout sessions, compute tax, issue invoices, or call payment
providers.

Asset package jobs export website ZIPs from cached extraction outputs. Render
jobs support deterministic `remotion-plan` output and local `mp4` or
`webm-alpha` rendering when `ffmpeg` is available. If `ffmpeg` is unavailable,
the job result reports `unavailable` through the existing exporter contract.
Render jobs preserve rights, lineage, audit metadata, and `aiUsage: none`.

Phase 3 extraction jobs register local run artifacts, including `run_config`,
`job_state`, `job_events`, `job_logs`, `job_metrics`, `artifact_manifest`,
`provider_diagnostics`, and failure diagnostics when a job fails. The API also
exposes `POST /v1/jobs/{jobId}/cancel` for cooperative cancellation and
`GET /v1/jobs/{jobId}/artifacts` for artifact listing.

Webhook delivery uses signed HMAC payloads and records local delivery rows. The
default worker transport records deliveries without making real network calls;
tests may inject a fake transport. See `docs/developer_api.md`.

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
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out /tmp/motionjson_phase15_demo --mask-provider threshold --lower-hsv 0,80,80 --upper-hsv 12,255,255 --sample-fps 12 --max-frames 12
```
