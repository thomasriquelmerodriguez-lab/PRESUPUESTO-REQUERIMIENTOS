#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p backups
stamp=$(date +%Y%m%d_%H%M%S)
file="backups/presupuesto_${stamp}.dump"
docker compose --env-file .env -f docker-compose.online.yml exec -T db pg_dump -U presupuesto -d presupuesto -Fc > "$file"
chmod 600 "$file"
echo "Respaldo creado: $file"
