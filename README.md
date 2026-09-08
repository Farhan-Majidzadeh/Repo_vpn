# Repo_vpn

Enterprise-oriented Telegram subscription management platform for Marzban or Sanaei/3x-ui.

## What is included

- FastAPI backend
- PostgreSQL + Redis
- Telegram bot (aiogram)
- Marzban adapter and 3x-ui adapter boundary
- Users, plans, subscriptions, node groups/nodes, service allocations
- Append-only usage and financial ledgers
- Idempotent payment-attempt model
- Docker deployment
- Health checks

## Deploy

```bash
cp .env.example .env
# fill PANEL_* and optional TELEGRAM_* values
./scripts/deploy.sh
```

API health:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/panel
```

Enable Telegram after setting `TELEGRAM_BOT_TOKEN`:

```bash
docker compose --profile telegram up -d bot
```

## Important REALITY note

A VLESS REALITY hostname such as `tr1.farrahan.ir` must resolve directly to the VPS and must not be orange-cloud proxied by Cloudflare. See `docs/REALITY-CLOUDFLARE.md`.

## Node.js note

This stack does **not require Node.js**. If an unrelated VPS task still needs NodeSource Node 22 and Jammy is stuck on `libnode-dev`/`common.gypi`, use `scripts/fix-node-jammy.sh`.

## Secrets

Never commit `.env`, Telegram bot tokens, panel passwords, private keys, or payment gateway secrets.

## Safe MVP admin access and tests

`POST /api/plans` and `POST /api/subscriptions` require `X-Admin-Key`
matching `APP_SECRET` using constant-time comparison. Missing, incorrect,
empty, and default development secrets are rejected with HTTP 403.
Telegram `/admin` and `/grant` accept only sender IDs in the comma-separated
`TELEGRAM_ADMIN_IDS` allowlist. `/grant` forwards `APP_SECRET` in `X-Admin-Key`.
The API and bot must use the same secret.

Run the full suite from the repository root with Python 3.12:

```bash
python -m pip install -r backend/requirements.txt -r bot/requirements.txt
python -m pytest -q
```

Tests use a fresh in-memory SQLite database per API test, the mock panel,
and mocked Telegram/HTTP calls. They do not read `.env`, require credentials,
or provision real customers. Keep `PANEL_KIND=mock` for local MVP exercises.
Payment processing is not implemented. Public user and subscription read
routes still need an authentication/ownership design before customer use.
