#!/bin/sh
set -eu

echo "[startup] 1/3 Aplicando migraciones de base de datos..."
alembic upgrade head
echo "[startup] Migraciones completadas."

echo "[startup] 2/3 Verificando datos iniciales..."
python -m app.seed
echo "[startup] Datos iniciales verificados."

DEFAULT_PORT=8000
if [ "${RENDER:-}" = "true" ]; then
  DEFAULT_PORT=10000
fi
APP_PORT="${PORT:-$DEFAULT_PORT}"

echo "[startup] 3/3 Iniciando servidor HTTP en 0.0.0.0:${APP_PORT}..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${APP_PORT}" \
  --workers "${WEB_CONCURRENCY:-1}" \
  --no-server-header
