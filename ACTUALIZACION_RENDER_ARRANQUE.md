# Actualización de arranque para Render

Esta versión corrige un bloqueo durante el despliegue en Render que impedía que Uvicorn alcanzara a abrir el puerto HTTP.

## Cambios

- El seed de PostgreSQL usa `pg_try_advisory_xact_lock`, evitando esperas indefinidas.
- Se añadieron límites de espera para bloqueos y consultas durante la carga inicial.
- La transacción del seed confirma datos una sola vez y libera automáticamente el bloqueo.
- El arranque muestra etapas explícitas en los logs de Render.
- En Render se usa `PORT` y, como respaldo, el puerto `10000`.
- `WEB_CONCURRENCY` usa 1 por defecto para evitar inicializaciones simultáneas.

## Logs esperados

```text
[startup] 1/3 Aplicando migraciones de base de datos...
[startup] Migraciones completadas.
[startup] 2/3 Verificando datos iniciales...
[seed] ...
[startup] Datos iniciales verificados.
[startup] 3/3 Iniciando servidor HTTP en 0.0.0.0:10000...
INFO: Application startup complete.
```

En Render mantenga `WEB_CONCURRENCY=1`.
