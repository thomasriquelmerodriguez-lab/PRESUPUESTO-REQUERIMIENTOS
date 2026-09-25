#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ -f .env ]] || { echo "Falta .env"; exit 1; }
docker compose --env-file .env -f docker-compose.online.yml build --pull app
docker compose --env-file .env -f docker-compose.online.yml up -d
docker image prune -f >/dev/null 2>&1 || true
docker compose --env-file .env -f docker-compose.online.yml ps
