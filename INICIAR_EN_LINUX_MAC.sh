#!/usr/bin/env sh
set -eu
docker compose up --build -d
printf 'Aplicación disponible en http://localhost:8000\n'
