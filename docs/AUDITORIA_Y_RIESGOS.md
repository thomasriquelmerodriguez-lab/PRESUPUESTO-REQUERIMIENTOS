# Auditoría, mejoras y riesgos mitigados

## Riesgos de la aplicación local anterior

| Riesgo anterior | Consecuencia posible | Tratamiento aplicado |
|---|---|---|
| Usuarios y clave dentro del HTML/JavaScript | Lectura y modificación desde DevTools | Usuarios y hashes trasladados al servidor y base de datos |
| Datos guardados en el navegador | Pérdida, mezcla de información y ausencia de concurrencia | PostgreSQL centralizado, transacciones e aislamiento por área |
| Validaciones solo en cliente | Manipulación directa de montos, áreas o permisos | Validación y autorización en cada operación del servidor |
| Sin protección CSRF | Operaciones forzadas desde otro sitio | Token CSRF, Origin/Referer y SameSite |
| Renderizado dinámico susceptible a XSS | Ejecución de código inyectado | Escape, CSP y límites de entrada |
| Sin control de edición concurrente | Sobrescritura silenciosa | Bloqueo temporal y versiones optimistas atómicas |
| Sin historial confiable | Imposibilidad de atribuir cambios | Logs de auditoría y eventos de seguridad |
| Carga de archivos sin aislamiento suficiente | Consumo excesivo o archivos maliciosos | Allowlist, límites de tamaño/dimensiones y control XLSX |
| Ausencia de integridad relacional | Registros incoherentes | FK, UNIQUE, CHECK, índices y migraciones |
| Aplicación de un solo equipo | Imposibilidad de trabajo simultáneo | Backend compartido, múltiples sesiones y sincronización SSE |

## Acciones auditadas

- Inicio y cierre de sesión.
- Intentos de autenticación fallidos.
- Creación, edición, bloqueo, desbloqueo y eliminación de requerimientos.
- Cambios de Obligado CAS.
- Vista previa y aplicación de presupuestos.
- Restauración de presupuesto base.
- Importación de respaldos.

Cada evento funcional registra usuario, fecha, IP, navegador, área, acción, entidad, resultado, request ID y detalles acotados. Los eventos de seguridad se almacenan en una tabla independiente.

## Riesgos residuales

- Una cuenta legítima comprometida puede realizar acciones dentro de sus permisos.
- La contraseña inicial compartida debe rotarse.
- Un administrador del servidor o de la base de datos tiene acceso privilegiado.
- La disponibilidad depende de la infraestructura y de la estrategia de respaldo.
- El navegador puede observar las rutas API que efectivamente utiliza; estas no contienen secretos.
- Los archivos Excel complejos pueden consumir recursos dentro de los límites configurados.
- La seguridad debe reevaluarse cuando se agreguen módulos, integraciones o acceso desde internet.

## Mejoras futuras recomendadas

1. Integración con identidad institucional mediante OIDC o SAML y MFA.
2. Panel de administración de usuarios y revisión periódica de accesos.
3. Cola de trabajos para importaciones muy grandes y reportes pesados.
4. Redis para sesiones, rate limiting y eventos en despliegues con muchas réplicas.
5. Almacenamiento inmutable o envío externo de logs de auditoría.
6. Métricas Prometheus, dashboards y alertas operativas.
7. Antivirus o sandbox de archivos en un flujo de carga corporativo.
8. Firma digital o folio verificable para reportes oficiales.
9. Políticas de retención, anonimización y eliminación conforme a normativa aplicable.
10. CI/CD con revisión de dependencias, SAST, DAST y despliegues firmados.
