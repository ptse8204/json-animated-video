# Billing And Pricing

Phase 19 adds a local plan catalog and entitlement status surface. It is
metadata only: no checkout, tax, invoice, payment collection, or payment
processor integration is implemented.

## Plans

The catalog lives in `motionjson.backend.billing` and is exposed through:

- `GET /v1/billing/plans`
- `GET /v1/billing/status`
- `python -m motionjson.cli backend list-plans`
- `python -m motionjson.cli backend billing-status`
- `MotionJSONClient.listBillingPlans()`
- `MotionJSONClient.billingStatus()`

Current plan ids:

- `starter`
- `studio`
- `production`

`MOTIONJSON_DEFAULT_PLAN` selects the local status plan. Unknown values fall
back to `starter`.

## Entitlement Metadata

Plan status returns limits for projects, monthly extracted frames, local asset
storage, webhook endpoints, creator packs, and seats. The values are intended
for UI gating and operational planning. They are not a payment ledger.

## Product Boundary

Billing status does not call AI providers, segmentation providers, checkout
services, tax services, invoice systems, or hosted payment APIs. It returns
`aiUsage: "none"`, `billingProvider: "local_catalog"`, and
`paymentCollection: "not_configured"`.

## Validation

```bash
pytest -q tests/test_backend_billing.py
npm test
git diff --check
```
