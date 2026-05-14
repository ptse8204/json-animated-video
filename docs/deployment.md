# Deployment Guide

MotionJSON ships a vendor-neutral local deployment surface. The default API
uses SQLite, `LocalStorageProvider`, and the Python stdlib HTTP server.

## Local API

```bash
python -m motionjson.cli backend init
python -m motionjson.cli backend serve-api \
  --db .motionjson/backend.sqlite \
  --storage-root .motionjson/storage \
  --host 127.0.0.1 \
  --port 8765
```

## Docker

```bash
docker build -t motionjson-ga .
docker run --rm -p 8765:8765 \
  -v motionjson-data:/data \
  motionjson-ga
```

## Docker Compose

```bash
docker compose config
docker compose up --build
```

The compose file persists `/data/backend.sqlite` and `/data/storage` to the
`motionjson-data` volume. `.env.example` contains empty optional provider
settings and no secrets.

## Operational Notes

- Keep `MOTIONJSON_BACKEND_DB` and `MOTIONJSON_STORAGE_ROOT` on durable storage.
- Put a TLS-terminating reverse proxy in front of the API for non-local use.
- Restrict API access to trusted clients and rotate API keys regularly.
- Keep hosted segmentation and LLM routes disabled unless an operator explicitly
  configures a provider and reviews data handling.
- Do not use provider keys in client-side examples or static pages.

## Validation

```bash
docker build -t motionjson-ga .
docker compose config
pytest -q tests/test_backend_billing.py tests/test_backend_api_product.py
git diff --check
```
