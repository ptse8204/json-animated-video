# Beta Readiness

Phase 17 adds a closed beta workflow and local observability surface for the
MotionJSON backend. MotionJSON remains AI object-layer editing for video and web
graphics: ingest/correction/labeling/optimization can use AI or segmentation,
while normal editing and preview use cached raster/alpha assets plus JSON
transforms.

## Closed Beta Setup

Initialize the local backend, create the first operator account, then grant that
account the explicit beta admin role:

```bash
python3 -m motionjson.cli backend init
printf '%s' "$ADMIN_PASSWORD" | python3 -m motionjson.cli backend create-user --email admin@example.com --password-stdin
export MOTIONJSON_SESSION_TOKEN="$(
  printf '%s' "$ADMIN_PASSWORD" | python3 -m motionjson.cli backend login --email admin@example.com --password-stdin | python3 -c 'import json,sys; print(json.load(sys.stdin)["sessionToken"])'
)"
python3 -m motionjson.cli backend bootstrap-beta-admin
```

`create-user` remains a local development/testing primitive. The documented
closed beta path is invite creation and invite acceptance.

## Invite Flow

Admins create expirable, revocable, one-time invite tokens:

```bash
python3 -m motionjson.cli backend create-beta-invite \
  --email beta-user@example.com \
  --role member \
  --ttl-seconds 604800
```

The response includes `inviteToken` once. SQLite stores only `token_hash` plus
invite metadata. Listing invites never returns raw token material:

```bash
python3 -m motionjson.cli backend list-beta-invites
python3 -m motionjson.cli backend revoke-beta-invite INVITE_ID
```

The invitee must authenticate as a local user with the same email and accept the
token:

```bash
python3 -m motionjson.cli backend accept-beta-invite --invite-token mjb_...
python3 -m motionjson.cli backend beta-status
```

Acceptance marks the invite accepted, creates or updates the beta member, and
prevents reuse.

## Admin Dashboard

The admin dashboard requires a beta member with role `admin`:

```bash
python3 -m motionjson.cli backend admin-dashboard
```

The REST endpoint is:

```http
GET /v1/admin/dashboard
Authorization: Bearer mj_local_...
```

The dashboard summarizes:

- beta invite and member counts
- job status counts, recent failures, and recent job events
- usage event count and cost dashboard
- unresolved feedback and unresolved error report counts

It excludes raw invite tokens, token hashes, API key hashes, webhook secrets,
storage keys, uploaded bytes, and private storage internals.

## Support And Feedback

Authenticated users can submit scoped feedback:

```bash
python3 -m motionjson.cli backend feedback \
  --project-id PROJECT_ID \
  --type bug \
  --severity normal \
  --subject "Timeline trim issue" \
  --message "The layer jumps after trim" \
  --context-json '{"browser":"local","url":"https://example.test/private?token=x"}'
```

Admins can list unresolved feedback:

```bash
python3 -m motionjson.cli backend feedback --admin-list
```

REST endpoints:

- `POST /v1/feedback`
- `GET /v1/admin/feedback`

## Error Reporting

Authenticated users can submit redacted error reports:

```bash
python3 -m motionjson.cli backend error-report \
  --project-id PROJECT_ID \
  --job-id JOB_ID \
  --message "Render failed" \
  --stack-trace "$STACK_TRACE" \
  --context-json '{"apiKey":"mj_local_secret","storage_key":"projects/p/upload.mov"}'
```

Admins can list unresolved error reports:

```bash
python3 -m motionjson.cli backend error-report --admin-list
```

REST endpoints:

- `POST /v1/error-reports`
- `GET /v1/admin/error-reports`

Feedback and error reports redact obvious bearer tokens, MotionJSON/API-like
keys, secret assignment values, URL query strings, sensitive context keys,
storage keys, and large context payloads.

## Validation

Phase 17 validation:

```bash
pytest -q tests/test_backend_beta_support.py tests/test_backend_api_product.py tests/test_backend_auth_projects_storage.py
npm test
npm run lint
git diff --check
```

Full project validation remains:

```bash
pytest -q
python3 -m motionjson.cli extract examples/demo_red_ball.mp4 --out out/demo --mask-provider threshold --max-frames 12
```
