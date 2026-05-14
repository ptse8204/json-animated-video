# Support Workflow

MotionJSON support for the closed beta is built around project-scoped feedback,
error reports, job events, and the beta admin dashboard.

## Intake

Use `POST /v1/feedback` or the CLI `backend feedback` command for product
feedback, workflow issues, unclear output, and beta onboarding problems. Use
`POST /v1/error-reports` or `backend error-report` for exceptions, failed
renders, failed extraction jobs, SDK errors, and client-side stack traces.

Include a `projectId` whenever possible. Include a `jobId` for worker or render
failures. Do not include raw uploads, API keys, invite tokens, webhook secrets,
or hosted provider credentials in support context.

## Triage

Beta admins review:

```bash
python3 -m motionjson.cli backend admin-dashboard
python3 -m motionjson.cli backend feedback --admin-list
python3 -m motionjson.cli backend error-report --admin-list
```

The dashboard is the first stop for counts and recent failures. Job events and
usage/cost dashboard data are local observability records. They do not trigger
AI calls during drag, scale, rotate, preview, or cached render inspection.

## Escalation

Escalate when:

- a closed beta user cannot accept an active invite
- feedback points to data exposure, secret leakage, or incorrect admin access
- error reports show repeated job failures for the same provider or project
- usage/cost records suggest provider boundaries were bypassed

Provider debugging must preserve MotionJSON boundaries: OpenRouter may route
LLM/VLM reasoning, but it is not a pixel segmentation engine. Segmentation and
matting providers remain separate and swappable.

## Local Validation

```bash
pytest -q tests/test_backend_beta_support.py
pytest -q tests/test_backend_api_product.py
npm test
git diff --check
```
