# Plan de pruebas

## Pruebas automatizadas incluidas

La entrega ejecutó 11 pruebas automatizadas sin fallos.

- Jerarquía de cuentas y casos especiales.
- Conteo de 180 cuentas migradas.
- Conteo de 655 requerimientos y monto total de $2.522.408.220.
- Aislamiento del usuario Salud frente al área Municipal.
- Rechazo de modificaciones sin token CSRF.
- Conflicto de edición de Obligado CAS con versión desactualizada.
- CSP, anti-clickjacking, no-sniff y no-cache.
- Cookie HttpOnly y SameSite=Strict.
- Rechazo de extensiones no permitidas.
- Entrada con apariencia de SQL tratada como dato de búsqueda.
- Ejecución de la migración Alembic y semilla sobre una base vacía.

## Pruebas manuales recomendadas

### Navegadores

- Chrome y Edge en Windows.
- Firefox en Windows/Linux/macOS.
- Safari en macOS, iPhone e iPad.
- Opera y Chrome Android.

### Resoluciones

- 320 px, 375 px, 768 px, 1024 px, 1366 px y pantallas anchas.
- Orientación vertical y horizontal.
- Zoom del navegador al 200 %.

### Flujos

- Inicio/cierre de sesión por cada rol.
- Cambio de área como Encargado.
- Creación y edición concurrente desde dos navegadores.
- Conflicto al modificar la misma cuenta CAS.
- Carga válida e inválida de XLS, XLSX y CSV.
- Presupuesto 2027 para cada área.
- Exportación CSV, respaldo JSON, restauración y reporte PDF.
- Sesión expirada y reconexión.
- Interrupción temporal de red.

## Pruebas de seguridad previas a producción

- SAST y análisis de dependencias.
- DAST autenticado.
- Prueba de autorización horizontal y vertical.
- Pruebas de fuerza bruta y rate limiting.
- Carga de archivos manipulados y bombas de compresión.
- Revisión de cabeceras TLS/HTTP.
- Prueba de penetración independiente.
