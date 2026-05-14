# MotionJSON Developer API

Phase 15 adds a local developer API for MotionJSON projects, assets, jobs,
asset packages, renders, and webhooks. It is dependency-light and uses the
stdlib HTTP server over the existing SQLite backend.

MotionJSON remains an AI object-layer editing system for video and web
graphics. API extraction uses existing backend provider policy: deterministic
local `threshold`, `external`, or `mock` mask providers. OpenRouter/LLMs are not
pixel segmentation engines and are not coupled to API extraction.

## API Keys

Create API keys with the backend CLI after logging in with a local session:

```bash
python -m motionjson.cli backend create-api-key \
  --session-token-env MOTIONJSON_SESSION_TOKEN \
  --name "local sdk"
```

The response includes `apiKey` once. The database stores only a SHA-256 hash,
prefix, timestamps, and scopes. Listing keys never returns raw key material:

```bash
python -m motionjson.cli backend list-api-keys --session-token-env MOTIONJSON_SESSION_TOKEN
python -m motionjson.cli backend revoke-api-key KEY_ID --session-token-env MOTIONJSON_SESSION_TOKEN
```

Use the raw key as a bearer token:

```http
Authorization: Bearer mj_local_...
```

## Running The API

```bash
python -m motionjson.cli backend serve-api \
  --db .motionjson/backend.sqlite \
  --storage-root .motionjson/storage \
  --host 127.0.0.1 \
  --port 8765
```

## Endpoints

- `POST /v1/projects`
- `GET /v1/projects`
- `GET /v1/projects/{projectId}`
- `POST /v1/projects/{projectId}/assets`
- `GET /v1/projects/{projectId}/assets`
- `GET /v1/assets/{assetId}`
- `GET /v1/assets/{assetId}/download`
- `POST /v1/projects/{projectId}/extractions`
- `GET /v1/projects/{projectId}/jobs`
- `GET /v1/jobs/{jobId}`
- `GET /v1/jobs/{jobId}/events`
- `POST /v1/projects/{projectId}/asset-packages`
- `POST /v1/projects/{projectId}/renders`
- `POST /v1/webhooks`
- `GET /v1/webhooks`
- `DELETE /v1/webhooks/{webhookId}`
- `GET /v1/webhook-deliveries`

Asset upload accepts JSON with `dataBase64`, `filename`, `kind`,
`contentType`, and optional `metadata`. This keeps the local server small and
avoids multipart dependencies.

## Asset Packages And Renders

Asset packages enqueue website ZIP exports from cached extraction outputs:

```json
{
  "sourceJobId": "extract_job_id",
  "format": "website-zip"
}
```

Render jobs enqueue cached-asset renders:

```json
{
  "sourceJobId": "extract_job_id",
  "format": "remotion-plan"
}
```

Supported render formats are `remotion-plan`, `mp4`, and `webm-alpha`.
`remotion-plan` is deterministic and does not invoke npm or network calls.
`mp4` and `webm-alpha` use local `ffmpeg` when available; otherwise the job
result reports `unavailable` through the existing exporter semantics. Render
jobs preserve rights, lineage, audit records, and `aiUsage: none`.

## Webhooks

Webhook endpoints are stored locally with generated signing secrets. The worker
records signed deliveries for `job.succeeded`, `job.failed`, `asset.created`,
`asset_package.ready`, and `render.ready` when matching endpoints are enabled.
The default worker transport records deterministic local deliveries and does
not make network calls; tests can inject a fake transport.

Webhook signatures use HMAC-SHA256 over:

```text
timestamp + "." + raw_body
```

The signature header format is:

```text
motionjson-signature: t=TIMESTAMP,v1=HEX_DIGEST
```

## JavaScript SDK

The SDK lives in `packages/motionjson-sdk` and exports `MotionJSONClient` plus
`verifyWebhookSignature`. It uses injected or global `fetch`, has no AI/provider
runtime dependency, and does not hardcode secrets.

```js
import { MotionJSONClient } from "@motionjson/sdk";

const client = new MotionJSONClient({
  baseUrl: "http://127.0.0.1:8765",
  apiKey: process.env.MOTIONJSON_API_KEY
});

const project = await client.createProject({ name: "Website motion" });
const asset = await client.uploadAsset(project.id, {
  filename: "clip.mp4",
  dataBase64: "...",
  kind: "source_video",
  contentType: "video/mp4"
});
const extraction = await client.createExtraction(project.id, {
  assetId: asset.id,
  maskProvider: "threshold",
  maxFrames: 12
});
const packageJob = await client.createAssetPackage(project.id, {
  sourceJobId: extraction.id
});
const renderJob = await client.createRender(project.id, {
  sourceJobId: extraction.id,
  format: "remotion-plan"
});
```

Validation:

```bash
pytest -q
npm test
npm run lint
git diff --check
```
