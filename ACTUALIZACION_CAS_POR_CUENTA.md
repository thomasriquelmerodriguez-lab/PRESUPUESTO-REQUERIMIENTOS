# Actualización — Obligado CAS por cuenta

Esta versión completa el tratamiento de **Obligado CAS** a nivel de cada cuenta presupuestaria.

## Cálculo

Para cada cuenta, el sistema calcula:

**Disponible por cuenta = Presupuesto vigente − Requerimientos ingresados de la cuenta − Obligado CAS de la cuenta**

## Municipal 2026

La migración `4a6b8c0d2e3f` recupera los valores históricos de Obligado CAS de la planilla municipal 2026 y los aplica por número de cuenta a todas las versiones 2026 existentes que todavía tengan CAS igual a cero. Los valores no cero que hayan sido editados manualmente se conservan.

## Nuevas modificaciones presupuestarias

- Si la nueva planilla trae la columna **OBLIGADO CAS**, esos valores son los que se cargan.
- Si la planilla no trae la columna **OBLIGADO CAS**, el sistema conserva automáticamente el CAS de la versión anterior para la misma cuenta.
- El Obligado CAS continúa siendo editable con el permiso `budgets.edit_cas`.

## Actualización sin perder datos

1. En la carpeta de la versión actual ejecute `docker compose down`.
2. **No use `-v`**.
3. Descomprima esta versión.
4. En la nueva carpeta ejecute `docker compose up --build -d`.
5. Alembic aplicará la migración automáticamente y conservará la base existente.
