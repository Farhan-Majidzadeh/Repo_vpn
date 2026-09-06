#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "Missing .env: cp .env.example .env and fill secrets" >&2; exit 1; }
docker compose pull db redis
docker compose build --pull api bot
docker compose up -d db redis api
sleep 3
curl -fsS http://127.0.0.1:8000/health
if grep -Eq '^TELEGRAM_BOT_TOKEN=.+$' .env; then
  docker compose --profile telegram up -d bot
fi
docker compose ps
