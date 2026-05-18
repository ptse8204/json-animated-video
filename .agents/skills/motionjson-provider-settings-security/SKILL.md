---
name: motionjson-provider-settings-security
description: Use for MotionJSON provider/model settings, bring-your-own-key API key UX, local/mock defaults, secret persistence, redaction, diagnostics, and hosted provider warnings.
---

# MotionJSON Provider Settings Security

Use this skill before changing provider registries, API key storage, model selection, diagnostics, settings endpoints, or provider settings UI.

## Defaults

- Mock/no-model mode must remain the first-run default.
- Local/free providers should be visually and behaviorally distinct from hosted/API-backed providers.
- Do not claim a provider is runnable unless capability checks prove it.

## API Key Handling

- Never commit real API keys, signed URLs, bearer tokens, or credential-bearing logs.
- Redact secrets in UI, API responses, diagnostics, logs, errors, exported settings, screenshots, and tests.
- Use stable redaction such as `sk-...abcd` or `<redacted:provider>` without exposing full values.
- Prefer environment variables for headless use and document precedence.
- If local persistence is implemented, describe where data is stored, how to delete it, and that local storage is not a managed secrets vault.

## Provider UX

Provider cards/settings should expose:

- local vs hosted;
- credential requirement;
- readiness status and setup action;
- model selector or custom model id where supported;
- capability tags;
- cost and privacy warning before hosted calls;
- safe test-connection behavior that does not leak keys.

## Tests

Add tests for:

- redaction helpers;
- settings persistence without secrets in exported views;
- missing/invalid key errors;
- provider/model selection;
- environment variable fallback;
- no credentials required for mock/local mode.
