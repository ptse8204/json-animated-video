# Provider API Keys

MotionJSON runs without provider credentials by default. The mock/no-model
Local UI path, red-ball CLI demo, local project review, and MotionJSON export
do not need SAM2, OpenRouter, hosted segmentation, or paid APIs.

Use provider keys only when you intentionally configure a hosted or optional
model-backed workflow.

## Supported Settings

The Local UI Provider settings panel currently covers:

- `mock`, `threshold`, `motion`, and `external`: local/free, no API key.
- `sam2-local`: local model choice only. SAM2 package and model paths still
  come from local installation and environment variables.
- `sam2-hosted`: hosted profile, model choice, API key, optional endpoint, and
  hosted-call opt-in. Built-in profiles include Replicate SAM2 video and a
  custom SAM2-compatible endpoint.
- `openai`: model choice and API key for hosted plan generation. It is not a
  segmentation provider and never receives frames from the UI-MODEL-04
  connector.
- `openrouter`: LLM/VLM model choice and API key for reasoning only. It is not
  a segmentation provider.
- `text_detector` and `class_detector`: local model-choice surfaces for
  scaffolded detector workflows.
- `auto_object_proposals`: no key in mock mode; optional local SAM2 automatic
  proposals use local package/checkpoint/config/device diagnostics, not a
  browser-supplied secret.
- `sam3-hosted`: hosted profile, model choice, API key, optional endpoint, and
  hosted-call opt-in. Built-in profiles include Roboflow SAM3 concept
  segmentation, Fal SAM3 image, and a custom SAM3-compatible endpoint. Setup
  tests validate fields locally, do not send frames or make network calls, and
  require a separate explicit opt-in for hosted smoke tests.

![Provider settings panel](../design/screenshots/phase-03b/laptop-1366-provider-settings.png)

## Where Keys Are Stored

Environment variables are preferred for headless and CLI use:

```bash
OPENROUTER_API_KEY=
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=openrouter/auto
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_DEFAULT_MODEL=gpt-5.4-mini
HOSTED_SEGMENTATION_URL=
HOSTED_SEGMENTATION_API_KEY=
REPLICATE_API_TOKEN=
ROBOFLOW_API_KEY=
ROBOFLOW_SAM3_URL=
FAL_KEY=
SAM3_HOSTED_URL=
SAM3_HOSTED_API_KEY=
SAM3_HOSTED_MODEL=auto
```

The Local UI can also save a provider key in the selected SQLite database,
usually `.motionjson/backend.sqlite`, in the `provider_settings` table for the
reserved local UI user. This is local persistence, not a managed secrets vault.
Use it for local development machines you control. Do not use it for public
demo instances unless you understand who can access the database file.

Environment variables take precedence over Local UI settings. If
`OPENROUTER_API_KEY` or `OPENAI_API_KEY` is set, diagnostics report the
credential source as `environment` even if a different Local UI key is saved.

Saved `sam2-hosted` and `sam3-hosted` settings are server-side runtime
settings for the Local UI worker. The browser never receives the raw key and
does not send the key back to the API. A hosted extraction still requires a run
config with explicit network/cost/privacy opt-in, and missing optional vendor
SDKs are reported as diagnostics instead of falling back to mock providers.

## What Is Redacted

The Local UI never returns raw provider keys from:

- `GET /api/provider-settings`
- `GET /api/capabilities`
- run-config validation responses
- provider setup checks
- local UI error responses
- screenshot captures

Display values use a shortened form such as `sk-...abcd`. Error text redacts
bearer tokens, `api_key=...`, `token=...`, `secret=...`, and common
OpenRouter/MotionJSON key shapes before returning them to the browser.

## Removing Keys

Use the Provider settings panel and choose `Reset` for the provider. This
removes the local settings row and saved provider key for that provider.

You can also remove all local UI provider settings by deleting the selected
local backend database:

```bash
rm .motionjson/backend.sqlite
```

That also removes local projects, users, jobs, and saved UI state in that
database. Keep or back up project data first if needed.

## Hosted Cost And Privacy

Local providers keep frames on your machine. Hosted providers may send frames,
frame-derived data, text prompts, or model-routing requests to a third-party
service. MotionJSON marks these providers as hosted, shows a cost/privacy
warning, and requires an explicit hosted-call opt-in in settings before hosted
segmentation can be considered for execution. The Local UI worker can use saved
`sam2-hosted` and `sam3-hosted` settings for explicit hosted runs, but it does
not put raw keys into API responses, run configs, logs, notebooks, screenshots,
or exported settings.

`POST /api/provider-settings/PROVIDER_ID/test` is a no-network setup check. It
verifies required fields and basic key shape, but it does not call OpenRouter
or a hosted segmentation service.

`POST /api/provider-settings/sam2-hosted/smoke-test` and
`POST /api/provider-settings/sam3-hosted/smoke-test` are explicit hosted SAM
smoke routes. They run only after the request acknowledgement. The
authenticated backend equivalents are:

```text
POST /v1/providers/sam2-hosted/smoke-test
POST /v1/providers/sam3-hosted/smoke-test
```

The smoke-test payload is:

```json
{
  "allowNetwork": true,
  "allowHosted": true,
  "acknowledgeCostPrivacy": true,
  "prompt": "object",
  "timeoutSeconds": 60,
  "retries": 1
}
```

Responses redact secrets and include `networkAttempted`. Failed setup or
missing acknowledgement returns before any hosted request is attempted.

OpenAI and OpenRouter remain reasoning-only. OpenAI can propose a reviewed run
plan in UI-MODEL-04, but MotionJSON still validates the generated config and
routes segmentation through explicit CV providers. Neither hosted reasoning
provider is a pixel segmentation engine or traces objects by itself.

## Safe Demo Guidance

- Codespaces and local CPU demos should use mock/no-model mode.
- Hugging Face Spaces or public demo deployments should not include provider
  keys in the repository, browser JavaScript, screenshots, or environment
  files visible to users.
- Colab notebooks should keep provider-key examples empty and prefer CLI
  no-model demos unless a user explicitly provides their own temporary key.
