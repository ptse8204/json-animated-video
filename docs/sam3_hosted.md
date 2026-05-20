# SAM3 Hosted Discovery

Hosted SAM3-compatible providers are optional and off by default. Use them only
when a user explicitly accepts that a generated smoke-test frame or real video
frames may leave the machine and may incur provider cost.

## Configuration

Headless and CLI workflows should prefer environment variables:

```bash
SAM3_HOSTED_URL=https://provider.example.test/sam3
SAM3_HOSTED_API_KEY=
SAM3_HOSTED_MODEL=auto
```

The Local UI Provider settings panel can also save the endpoint, API key, model
choice, and hosted-call opt-in in the local SQLite database. Raw keys are never
returned by `GET /api/provider-settings` or `GET /api/capabilities`.

Do not put hosted API keys in extraction run configs. The hosted SAM3 runtime
adapter reads credentials from environment variables or explicit server-side
settings paths so job payloads do not become a secret store.

## Setup Check Versus Smoke Test

`POST /api/provider-settings/sam3-hosted/test` is setup-only. It validates that
the endpoint, key, and model fields are present and plausible, then returns
`networkAttempted: false`.

`POST /api/provider-settings/sam3-hosted/smoke-test` is the only Local UI route
that sends a test frame. It requires:

```json
{
  "allowNetwork": true,
  "allowHosted": true,
  "acknowledgeCostPrivacy": true,
  "prompt": "object"
}
```

The authenticated API equivalent is:

```text
POST /v1/providers/sam3-hosted/smoke-test
```

Both routes use server-side credentials from environment variables or saved
Local UI settings. The browser does not send the raw key back to the backend.

## Runtime Contract

The hosted adapter posts JSON with:

- `model`: selected model id, defaulting to `auto`;
- `task`: `sam3_smoke_test`, `sam3_concept`, `sam3_exemplar`,
  `sam3_auto_masks`, or `sam3_track_candidate`;
- `frame`: a PNG base64 frame for image discovery/smoke tests;
- `prompt`, `exemplars`, `box`, or `mask` depending on task;
- `maxCandidates`, timeout, and retry behavior controlled by request/config.

The response must be a SAM3-compatible JSON object or list containing masks,
boxes, scores, labels, outputs, objects, tracks, predictions, segments, or
instances. Empty candidate responses fail schema validation instead of being
treated as success.

## Safety Rules

- No hosted network request is made by setup checks.
- A smoke or runtime request requires explicit network and cost/privacy
  acknowledgement.
- Secrets are redacted from responses, diagnostics, errors, screenshots, and
  docs.
- Hosted providers remain marked as network-required and provider-billed.
- The base CPU/mock install does not depend on hosted SAM3.
