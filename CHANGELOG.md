
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

## 2026-09-25 — Jerarquía presupuestaria
- Corrige doble contabilización de filas padre e hijas al cargar presupuestos.
- Soporta jerarquía explícita `22-00 > 22-01 > 22-01-001/002` y su equivalente con prefijo `215-`.
- Recalcula automáticamente metadatos y total de presupuestos existentes mediante Alembic.
- Mantiene compatibilidad con planillas que no incluyen la fila resumen superior.

## 2026-09-25 — Total por primer orden jerárquico
- El total del presupuesto importado suma exclusivamente cuentas de orden 1.
- Las cuentas hijas ya no se promueven al total si falta una fila padre.
- La vista previa informa cuántas cuentas de primer orden detectó y muestra el orden de cada fila.
- Se incorpora una migración conservadora para corregir versiones activas cuando existe cobertura completa de cuentas de primer orden.

## 2026-09-29 - Suma por niveles jerárquicos

- El presupuesto se recalcula de abajo hacia arriba en cada rama contable.
- Las cuentas padre con hijos toman como presupuesto la suma de sus hijos calculados.
- Las cuentas detalle conservan el monto cargado en la planilla.
- El total general sigue sumando solo las cuentas de primer orden.
- La vista previa muestra monto original y monto jerárquico calculado.
- Se agrega la migración `7d9e1f3a5b6c` para recalcular presupuestos existentes.

## Reemplazo de presupuesto y eliminación de cargas

- La actualización de un presupuesto ahora reemplaza valores por código de cuenta; nunca suma el monto nuevo al anterior.
- Se admiten actualizaciones parciales: cuentas existentes se reemplazan, cuentas nuevas se incorporan y cuentas omitidas se conservan.
- El total vigente se calcula únicamente desde las cuentas de primer orden del snapshot resultante.
- Los montos de cuentas padre cargados en la planilla se conservan como valores vigentes y no son sobrescritos por una suma automática de hijos.
- La vista previa muestra presupuesto anterior, presupuesto resultante y cantidad de cuentas nuevas/modificadas/conservadas.
- Se agregó eliminación de versiones cargadas por usuario.
- Si se elimina la versión activa, se restaura automáticamente la versión anterior disponible.
- La base incorporada no se puede eliminar.

## 2.4.0 - Eliminación de versiones de presupuesto

- Se agrega **Eliminar versión** a todas las versiones disponibles en Actualizar presupuesto.
- Se permite eliminar versiones históricas, activas y base incorporada.
- Al eliminar la activa se restaura la versión anterior más reciente cuando existe.
- Si no queda ninguna versión, el año permanece creado sin presupuesto activo.
- Se evita que una base eliminada voluntariamente reaparezca al reiniciar/desplegar.
