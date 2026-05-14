# Privacy And Data Handling

MotionJSON beta backend data is local SQLite metadata plus local
`StorageProvider` bytes. The product model is reusable motion layers controlled
by JSON with cached raster/alpha assets for photoreal objects.

## Stored Data

The backend stores:

- user emails, password hashes, session token hashes, and API key hashes
- project, asset, job, queue, usage, rights, lineage, audit, and webhook records
- beta invite metadata with hashed invite tokens only
- beta member role metadata
- feedback and error reports with redacted context
- local billing plan status derived from configuration

The backend does not store raw API keys after first response, raw invite tokens
after first response, or raw session tokens. Admin dashboard responses do not
include API key hashes, invite token hashes, webhook signing secrets, storage
keys, uploaded file bytes, or private storage internals.

Billing/pricing routes expose local catalog and entitlement metadata only. They
do not store payment methods, tax identifiers, invoice data, or checkout
sessions.

## Redaction

Feedback and error reports redact or truncate:

- bearer tokens and API-key-like values
- `api_key=`, `token=`, `secret=`, `password=`, and authorization assignments
- sensitive context keys such as `apiKey`, `authorization`, `dataBase64`,
  `password`, `secret`, `signingSecret`, `storage_key`, and `token`
- URL query strings
- large text, stack traces, lists, and nested context payloads

Redaction is a defensive local safeguard, not a license to send secrets. Beta
users should still avoid submitting credentials or raw uploaded media in support
payloads.

## Provider Boundary

AI should run mainly at ingest, correction, labeling, and optimization time.
Editing and preview use cached assets and JSON transforms. Provider interfaces
remain swappable:

- `LLMProvider`
- `SegmentationProvider`
- `MattingProvider`
- `RenderProvider`
- `StorageProvider`
- `ExportProvider`

OpenRouter may be used for LLM/VLM model routing. It is not the pixel
segmentation engine and is not accepted by backend extraction as a segmentation
provider.

## Validation

```bash
pytest -q
npm test
npm run lint
git diff --check
```
