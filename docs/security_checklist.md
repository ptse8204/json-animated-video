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

## API Exposure

- Bind to `127.0.0.1` for local use.
- Use TLS and a reverse proxy for network exposure.
- Restrict ingress to trusted networks or authenticated clients.
- Keep raw API keys server-side; public pages should use static manifests only.
- Review webhook URLs before enabling delivery outside local tests.

## Data Handling

- Treat uploaded videos, cached cutouts, masks, and alpha assets as user media.
- Verify source rights and creator approval before making creator packs.
- Use support/error-report redaction as a fallback, not as permission to submit
  secrets or raw private media.
- Keep OpenRouter or other LLM/VLM routing separate from segmentation.
- Keep hosted segmentation disabled unless explicitly configured.

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
git diff --check
```
