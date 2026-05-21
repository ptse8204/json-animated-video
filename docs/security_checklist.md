# Security Checklist

Use this checklist before sharing a MotionJSON backend beyond a local machine.

## Secrets

- Keep `.env` files out of git.
- Use `.env.example` only for empty placeholders and local defaults.
- Store API keys, session tokens, invite tokens, and hosted provider credentials
  in environment variables or a secret manager.
- Rotate API keys and revoke unused sessions.
- Never put provider keys in examples, public pages, SDK tests, or browser
  runtime code.
- Confirm issue templates, screenshots, phase reports, diagnostics, and support
  bundles do not contain provider keys, bearer tokens, signed URLs, private
  media, full local paths, SQLite databases, or credential-bearing logs.

## API Exposure

- Bind to `127.0.0.1` for local use.
- Use TLS and a reverse proxy for network exposure.
- Restrict ingress to trusted networks or authenticated clients.
- Keep raw API keys server-side; public pages should use static manifests only.
- Review webhook URLs before enabling delivery outside local tests.

## Model Connector And Hosted Providers

- Keep mock/no-model and local/free providers available as the default path.
- Never make a hosted OpenAI, OpenRouter, SAM-style, detector, or segmentation
  call without explicit hosted-call opt-in and per-request cost/privacy
  acknowledgement.
- Treat model-planner output as a proposed run plan. Validate generated configs
  before enqueueing extraction jobs.
- Keep segmentation and tracking routed through explicit CV providers; an LLM
  or VLM planner is not a pixel segmentation provider.
- Store hosted provider credentials server-side only. UI/API responses,
  diagnostics, logs, screenshots, and exports must return redacted values or
  credential presence, not raw secrets.

## Data Handling

- Treat uploaded videos, cached cutouts, masks, and alpha assets as user media.
- Verify source rights and creator approval before making creator packs.
- Use support/error-report redaction as a fallback, not as permission to submit
  secrets or raw private media.
- Keep OpenRouter or other LLM/VLM routing separate from segmentation.
- Keep hosted segmentation disabled unless explicitly configured.

## Repository Safeguards

- Enable private vulnerability reporting, secret scanning, and push protection.
- Enable Dependabot alerts and grouped updates for Python, npm, GitHub Actions,
  and Docker manifests.
- Protect the default branch with required reviews and required CI checks.
- Keep the Apache-2.0 `LICENSE` and package metadata in sync before publishing
  reusable releases or advertising redistribution/commercial rights.
- Use protected or signed release tags for release candidates when available.
- Keep Codex/GitHub automation from pushing commits, publishing packages,
  changing provider settings, or making hosted calls without human review.

## Deployment

- Persist SQLite and storage roots on durable volumes.
- Back up the database and storage together.
- Run `git diff --check` and the relevant test commands before release.
- Scan public HTML and docs for remote scripts, credential names with values,
  and product framing drift.

## Validation

```bash
pytest -q tests/test_ga_launch_docs.py tests/test_backend_billing.py
npm run lint
python3 scripts/capture_docs_assets.py --check
git diff --check
```
