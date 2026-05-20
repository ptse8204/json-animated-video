# Phase OD-09 Report: Hosted SAM3 Adapter

## Summary

Added hosted SAM3-compatible discovery support behind explicit cost/privacy and
network gates.

The provider layer now has a `HostedSAM3DiscoveryBackend` with setup status,
one-frame smoke testing, concept/exemplar/auto-mask request helpers, selected
candidate tracking requests, timeout/retry handling, and SAM3-style response
normalization. Runtime config can choose the hosted path with
`providerPreference: "sam3-hosted"` or `hosted: true`, but it still refuses to
send frames unless `allowNetwork` and `acknowledgeCostPrivacy` are both true.
Run configs do not read API keys; hosted credentials come from environment
variables or server-side provider settings.

The Local UI and authenticated API now expose explicit hosted SAM3 smoke-test
routes. The normal provider setup check remains no-network. Smoke responses
redact credentials, report `networkAttempted`, and fail before transport calls
when setup or acknowledgement is missing.

## Changed Files

- `README.md`
- `docs/discovery_providers.md`
- `docs/index.md`
- `docs/provider_capabilities.md`
- `docs/run_config.md`
- `docs/security/api_keys.md`
- `docs/sam3_hosted.md`
- `docs/roadmap/phase-od-09-report.md`
- `src/motionjson/backend/api.py`
- `src/motionjson/capabilities.py`
- `src/motionjson/provider_settings.py`
- `src/motionjson/providers/discovery.py`
- `src/motionjson/providers/sam3.py`
- `src/motionjson/ui/server.py`
- `src/motionjson/ui/static/app.js`
- `tests/test_phase03b_provider_settings_ui.py`
- `tests/test_provider_settings.py`
- `tests/test_sam3_providers.py`

## Tests Run

- `python3 -m py_compile src/motionjson/providers/sam3.py src/motionjson/providers/discovery.py src/motionjson/capabilities.py src/motionjson/provider_settings.py src/motionjson/ui/server.py src/motionjson/backend/api.py tests/test_sam3_providers.py tests/test_provider_settings.py tests/test_phase03b_provider_settings_ui.py`
- `python3 -m pytest tests/test_sam3_providers.py tests/test_provider_settings.py tests/test_capabilities.py tests/test_backend_api_product.py tests/test_phase03b_provider_settings_ui.py tests/test_docs_links.py -q`
- `python3 -m pytest -q`
- `python3 -m motionjson.cli --help`
- `python3 -m motionjson.cli extract --help`
- `python3 -m motionjson.cli backend --help`
- `python3 -m motionjson.cli ui --help`
- Expected failure check: hosted SAM3 extraction without `allowNetwork` and
  `acknowledgeCostPrivacy` exits with
  `sam3-hosted requires explicit allowNetwork=true and acknowledgeCostPrivacy=true before sending frames.`
- `python3 -m motionjson.cli backend diagnostics --json`
- `npm test`
- `npm run lint`
- `npm run build`
- `npm run embed:smoke`
- `npm run ui:layout -- --check`
- `python3 -m pytest tests/test_docs_links.py tests/test_docs_assets.py -q`
- `python3 scripts/capture_docs_assets.py --check`
- `git diff --check`

## Risk Review

The requested plan-risk and diff-review scouts could not run because the
thread limit was reached. The master agent performed the review in-thread,
focusing on no-network setup checks, explicit hosted smoke acknowledgement,
redaction, avoiding run-config secrets, response schema validation, docs
truthfulness, and API route consistency.

## Known Limitations

- No real hosted SAM3 endpoint was called in this environment. Tests use
  injected fake transports and validate request/response contracts.
- Hosted SAM3 request payloads are intentionally generic because providers may
  expose different SAM3-compatible APIs. Additional adapter normalization may
  be needed after testing against a real endpoint.
- Saved Local UI hosted credentials are used for setup and explicit smoke
  tests. Normal extraction jobs should use environment credentials or explicit
  server-side runtime wiring.

## Follow-Up Tasks

- Run the hosted smoke route against a real provider endpoint with temporary
  credentials and confirm the response schema.
- Add endpoint-specific adapters if a hosted provider does not match the generic
  SAM3-style JSON contract.
- Expand UI copy around saving settings before running a hosted smoke test if
  users find the current flow unclear.
