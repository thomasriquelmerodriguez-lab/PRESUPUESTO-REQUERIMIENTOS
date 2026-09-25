# Arquitectura de la solución

## 1. Capas

### Presentación

- Plantillas HTML semánticas.
- CSS Mobile First con puntos de quiebre para teléfono, tablet y escritorio.
- JavaScript modular para estado de interfaz, llamadas API y páginas funcionales.
- Sin claves, hashes, presupuestos incrustados ni reglas de autorización en el cliente.

### API

- Rutas separadas para autenticación, requerimientos, presupuestos, reportes, auditoría, sincronización y respaldos.
- Esquemas Pydantic para validar tipos, longitudes, rangos y formatos.
- Respuestas de error homogéneas sin trazas internas.

### Servicios de dominio

- Cálculo del disponible presupuestario.
- Versionamiento de presupuestos.
- Reglas de acceso por área.
- Bloqueos temporales y control optimista de versiones.
- Importación y normalización de cuentas.
- Auditoría y eventos de sincronización.

### Persistencia

- SQLAlchemy como capa de acceso a datos.
- PostgreSQL como base principal.
- Índices compuestos para filtros frecuentes.
- Claves foráneas, restricciones únicas y restricciones CHECK.
- Transacciones para operaciones que afectan presupuesto y registros.
- Alembic para cambios de esquema controlados.

### Infraestructura y seguridad

- Caddy como terminador TLS y proxy inverso.
- Cookies de sesión seguras.
- Cabeceras HTTP defensivas.
- Logs JSON con identificador de solicitud.
- Docker para entornos reproducibles.

## 2. Flujo de una operación crítica

Ejemplo: creación de un requerimiento.

1. El navegador envía datos mediante HTTPS, cookie HttpOnly y token CSRF.
2. El servidor valida sesión, origen, token CSRF y permiso sobre el área.
3. Pydantic valida el formato y los límites de cada campo.
4. El servicio bloquea la fila de la cuenta presupuestaria durante la transacción.
5. El servidor vuelve a calcular el disponible con datos actuales.
6. La operación se guarda o se rechaza si existe conflicto.
7. Se registra auditoría y se emite un evento para actualizar otras sesiones.
8. La transacción se confirma de forma atómica.

## 3. Concurrencia

- Cada navegador mantiene una sesión independiente almacenada en la base de datos.
- Los requerimientos usan `version` para detectar ediciones desactualizadas.
- La edición visual utiliza un bloqueo temporal de cinco minutos.
- La adquisición del bloqueo es atómica para impedir que dos usuarios lo obtengan al mismo tiempo.
- Obligado CAS usa `row_version` y actualización condicional.
- La disponibilidad de una cuenta se valida dentro de una transacción con bloqueo de fila.
- Las cargas de nuevas versiones presupuestarias se serializan por área.
- Server-Sent Events informa cambios a las demás sesiones conectadas.

## 4. Extensibilidad

Las áreas no están codificadas dentro de cada operación de negocio: se modelan en tablas y membresías. Se pueden incorporar nuevas áreas, roles, módulos o reportes mediante nuevos servicios y routers, sin reescribir los módulos existentes.

## 5. Decisiones de diseño

- Se evitó un framework frontend pesado porque la aplicación es principalmente formularios, filtros y listas. Esto reduce descarga, memoria y superficie de dependencias.
- Se eligieron sesiones de servidor en lugar de guardar tokens de autenticación en almacenamiento web.
- Se conservaron los datos originales como archivos de semilla versionados, permitiendo reproducir la migración.
- Los reportes se generan en el servidor para evitar que el cliente altere totales o reglas de filtrado.
