#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "Uso: bash scripts/online/restaurar.sh /ruta/respaldo.dump"
  exit 1
fi
cd "$(dirname "$0")/../.."
file="$1"
[[ -f "$file" ]] || { echo "No existe: $file"; exit 1; }
echo "ATENCION: esto reemplazará los datos actuales."
read -r -p "Escriba RESTAURAR para continuar: " confirm
[[ "$confirm" == "RESTAURAR" ]] || exit 1
docker compose --env-file .env -f docker-compose.online.yml exec -T app true
docker compose --env-file .env -f docker-compose.online.yml exec -T db dropdb -U presupuesto --if-exists presupuesto
docker compose --env-file .env -f docker-compose.online.yml exec -T db createdb -U presupuesto presupuesto
cat "$file" | docker compose --env-file .env -f docker-compose.online.yml exec -T db pg_restore -U presupuesto -d presupuesto --no-owner --no-privileges
# Asegura esquema actualizado después de restaurar.
docker compose --env-file .env -f docker-compose.online.yml exec -T app alembic upgrade head
echo "Restauración finalizada."
