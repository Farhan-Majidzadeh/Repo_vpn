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
- Durable card-transfer orders with plan snapshots and idempotency keys
- Admin approval, rejection, and reconciliation flow
- Docker deployment
- Health checks

## Deploy

```bash
cp .env.example .env
# fill PANEL_* and TELEGRAM_* values
# set PAYMENT_INSTRUCTIONS locally; never commit real banking details
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

## Telegram card-transfer flow

1. User runs `/plans` and then `/buy <plan_id>`.
2. The bot creates an idempotent pending order and displays `PAYMENT_INSTRUCTIONS`.
3. The administrator independently verifies the transfer.
4. Administrator runs `/approve <order_id>` or `/reject <order_id>`.
5. Approval provisions exactly one subscription using a deterministic panel username.
6. If an external-panel result is uncertain, `/reconcile <order_id>` safely resumes the order.
7. User checks `/orders` and `/my` for order and service status.

Online payment-gateway callbacks are intentionally not enabled yet. Card-transfer approval is the usable payment path in this MVP.

## Important REALITY note

A VLESS REALITY hostname such as `tr1.farrahan.ir` must resolve directly to the VPS and must not be orange-cloud proxied by Cloudflare. See `docs/REALITY-CLOUDFLARE.md`.

## Node.js note

This stack does **not require Node.js**. If an unrelated VPS task still needs NodeSource Node 22 and Jammy is stuck on `libnode-dev`/`common.gypi`, use `scripts/fix-node-jammy.sh`.

## Secrets

Never commit `.env`, Telegram bot tokens, panel passwords, private keys, payment instructions containing real account details, or payment gateway secrets.

## Admin access and tests

`POST /api/plans`, `POST /api/subscriptions`, and all order mutation/read endpoints used by the bot require `X-Admin-Key` matching `APP_SECRET` using constant-time comparison. Missing, incorrect, empty, and default development secrets are rejected with HTTP 403.

Telegram `/admin`, `/grant`, `/approve`, `/reject`, and `/reconcile` accept only sender IDs in the comma-separated `TELEGRAM_ADMIN_IDS` allowlist. The API and bot must use the same `APP_SECRET`.

Run the full suite from the repository root with Python 3.12:

```bash
python -m pip install -r backend/requirements.txt -r bot/requirements.txt
python -m pytest -q
```

Tests use a fresh in-memory SQLite database per API test, the mock panel, and mocked Telegram/HTTP calls. They do not read `.env`, require credentials, transfer money, or provision real customers. Keep `PANEL_KIND=mock` for local MVP exercises.

The API is currently intended to remain bound to localhost behind the bot/reverse-proxy boundary. Public user and subscription reads still need a dedicated end-user authentication/ownership layer before direct public API exposure.
