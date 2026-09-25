#!/usr/bin/env python3
from __future__ import annotations
import getpass
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[2]
out = root / ".env"
if out.exists():
    raise SystemExit("Ya existe .env. No se sobrescribió.")

domain = input("Dominio (ej. presupuesto.municipalidad.cl): ").strip().lower()
if not domain or "://" in domain or "/" in domain:
    raise SystemExit("Dominio inválido. Use solo el host, sin https:// ni rutas.")
initial = getpass.getpass("Clave inicial temporal para usuarios semilla: ").strip()
if len(initial) < 8:
    raise SystemExit("Use una clave inicial de al menos 8 caracteres para producción.")

pg = secrets.token_urlsafe(36)
secret = secrets.token_urlsafe(64)
content = f"""APP_DOMAIN={domain}\nAPP_ORIGIN=https://{domain}\nPOSTGRES_PASSWORD={pg}\nSECRET_KEY={secret}\nINITIAL_PASSWORD={initial}\nSESSION_IDLE_MINUTES=30\nSESSION_ABSOLUTE_HOURS=8\nSESSION_TOUCH_SECONDS=60\nLOGIN_ATTEMPTS=5\nLOGIN_WINDOW_MINUTES=15\nUPLOAD_MAX_BYTES=10485760\nIMPORT_MAX_ROWS=100000\nIMPORT_MAX_COLUMNS=100\nXLSX_MAX_UNCOMPRESSED_BYTES=125829120\nLOG_LEVEL=INFO\nWEB_CONCURRENCY=2\n"""
out.write_text(content, encoding="utf-8")
try:
    out.chmod(0o600)
except OSError:
    pass
print(f"Creado: {out}")
print("Guarde una copia segura de .env y no la publique ni la envíe por correo.")
