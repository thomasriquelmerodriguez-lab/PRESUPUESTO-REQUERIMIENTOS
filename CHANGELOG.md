
## Obligado CAS por cuenta — 2026-08-11
- Backfill de Obligado CAS municipal 2026 por código de cuenta en todas las versiones existentes.
- Disponible por cuenta calculado explícitamente como presupuesto menos requerimientos menos CAS.
- Conservación automática de CAS al cargar una modificación presupuestaria que no incluya columna CAS.
- Si la nueva planilla sí incluye CAS, sus valores prevalecen.
# Changelog

## 2.3.0 - Gestión de años presupuestarios

- Se incorpora un registro explícito de años presupuestarios por área.
- Los usuarios con privilegio `budgets.import` pueden crear nuevos años entre 2020 y 2100.
- Cada año queda aislado por área: Municipal, Salud y Educación pueden tener presupuestos diferentes para el mismo año.
- La carga de planillas ahora exige seleccionar un año previamente creado.
- Se muestra el estado de cada año: con presupuesto o pendiente de carga.
- Al aplicar una planilla, el año queda automáticamente asociado a su versión de presupuesto vigente.
- Los años existentes se migran automáticamente desde las versiones ya almacenadas, sin perder información.
- Se conserva la misma base de datos Docker mediante el nombre estable del proyecto y volumen.

# Registro de cambios

## 2.0.0 — Refactorización profesional

- Migración de aplicación HTML local a arquitectura cliente-servidor.
- PostgreSQL, SQLAlchemy y Alembic.
- Argon2id, sesiones de servidor, CSRF, RBAC y rate limiting.
- Separación segura de Municipal, Salud y Educación.
- Auditoría, eventos de seguridad y logs JSON.
- Control de concurrencia para requerimientos y Obligado CAS.
- Sincronización de sesiones mediante Server-Sent Events.
- Importación segura de XLS/XLSX/CSV y respaldos JSON.
- Diseño Mobile First, accesibilidad y estados de carga/error.
- Preservación de 655 requerimientos y 180 cuentas de 2026.
- Contenedores para desarrollo y producción con HTTPS mediante Caddy.

## 2.1.0 - 2026-08-06

- Se agregó administración de usuarios, áreas y privilegios granulares.
- Se agregó selector de usuarios activos en el inicio de sesión.
- Se implementó autorización por permiso en todos los módulos y endpoints.
- Se agregó revocación de sesiones al cambiar clave, estado, áreas o privilegios.
- Se agregaron eventos de auditoría para creación, actualización y restablecimiento de claves.
- Se agregó migración Alembic para la tabla `user_permissions`.
