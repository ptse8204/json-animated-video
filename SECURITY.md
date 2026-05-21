# Security Policy

MotionJSON is local-first. It can process private media, local database files,
provider credentials, and optional hosted model endpoints, so security reports
should avoid attaching private videos, secrets, or full local paths.

## Supported Versions

This repository is pre-1.0. Security fixes target the `main` branch until a
stable release policy is published.

## Reporting A Vulnerability

Use GitHub private vulnerability reporting or a private maintainer contact when
available. If no private channel is available, open a public issue with a
minimal description and omit exploit details, secrets, private media, local
paths, and credentials until a maintainer can move the discussion to a private
channel.

For non-sensitive bugs, use a normal GitHub issue.

## Secrets And Local Data

- Do not commit `.env`, provider API keys, hosted segmentation credentials,
  SQLite databases, `.motionjson/`, or generated private media outputs.
- Keep hosted segmentation and LLM/VLM providers disabled unless the operator
  explicitly configures credentials and reviews the data boundary.
- Keep model API keys and hosted provider tokens server-side. Browser code,
  API responses, diagnostics, logs, screenshots, exports, tests, and issue
  templates should show only redacted values or credential presence.
- Do not make hosted OpenAI/OpenRouter planner, hosted SAM-style, detector, or
  segmentation calls without explicit hosted-call opt-in and per-request
  cost/privacy acknowledgement.
- Rotate any key that was pasted into logs, screenshots, issue text, or sample
  configs.
- Use `python3 -m motionjson.cli backend diagnostics --json` to confirm which
  optional providers are installed, configured, and runnable before sharing a
  reproduction.

## Repository Safeguards

Maintainers should enable private vulnerability reporting, secret scanning,
push protection, Dependabot alerts, grouped dependency updates, protected
branches, required CI checks, and protected or signed release tags before
publishing release candidates. A reusable public release also needs an explicit
`LICENSE` file; this repository snapshot does not grant reuse, redistribution,
or commercial rights without one.
