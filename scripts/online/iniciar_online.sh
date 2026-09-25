#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
[[ -f .env ]] || { echo "Falta .env. Ejecute: python3 scripts/online/generar_env.py"; exit 1; }
docker compose --env-file .env -f docker-compose.online.yml up -d --build
docker compose --env-file .env -f docker-compose.online.yml ps
