# Repo_vpn

Production-oriented Telegram sales platform for provisioning subscriptions on
Marzban and Sanaei/3x-ui panels.

## Milestone M1

M1 delivers a private-beta purchase path:

1. A customer selects a 30-day traffic package in Telegram.
2. The API creates an order priced in integer toman.
3. A real payment adapter creates and verifies the transaction.
4. The allocator selects a healthy, compatible provisioning target.
5. A provider adapter provisions the service on Marzban or 3x-ui.
6. The subscription URL is returned to the customer.

The first production payment adapter is intentionally not selected yet. M1 is
not complete until merchant credentials are available and one real low-value
transaction succeeds end to end. Test doubles may be used by automated tests,
but no simulated gateway is enabled in production.

## Architecture

- `api`: FastAPI HTTP API and health checks
- `bot`: aiogram Telegram bot
- `worker`: background-job entry point; transactional outbox processing is an M1 follow-up
- `db`: PostgreSQL 16
- `redis`: Redis queue and coordination service
- `PanelAdapter`: common boundary for Marzban and Sanaei/3x-ui
- `PaymentProvider`: gateway-neutral payment boundary

The platform distinguishes a panel from a provisioning target. A Marzban
target can represent a panel plus a user/inbound/host policy, while a 3x-ui
target can represent a panel plus a group of inbound IDs.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API endpoints:

- `GET /health/live`
- `GET /health/ready`
- `GET /api/v1/packages`

Run local tests:

```bash
python -m pip install -e '.[dev]'
pytest
```

## Security rules

- Never commit Telegram tokens, panel credentials, merchant IDs, or API keys.
- A payment callback never proves payment by itself; the backend must verify it
  server-to-server with the selected gateway.
- Provider references and provisioning idempotency keys are unique.
- Prices are stored as integer toman. Provider-specific unit conversion happens
  only inside the payment adapter.
- Start production with `SALES_MODE=private_beta` and an explicit Telegram ID
  allowlist before changing it to `public`.

## Current status

This branch contains the M1 foundation: runnable services, initial database
schema, package catalog endpoint, bot entry point, adapter contracts, allocation
policy, and tests. Real payment and panel integrations remain subsequent M1
issues.
