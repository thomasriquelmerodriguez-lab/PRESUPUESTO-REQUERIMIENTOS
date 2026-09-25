# Seguridad por diseño y defensa en profundidad

## Controles implementados

### Autenticación

- Contraseñas almacenadas con Argon2id, sal aleatoria y parámetros de costo configurados.
- Mensaje genérico para usuario o clave incorrectos.
- Verificación con hash ficticio cuando el usuario no existe, reduciendo diferencias de tiempo.
- Bloqueo temporal y limitación de intentos por combinación de usuario e IP.
- Registro de intentos fallidos como eventos de seguridad.
- Script seguro para cambiar claves y revocar todas las sesiones del usuario.

### Sesiones

- Token aleatorio de alta entropía; en la base solo se conserva su SHA-256.
- Cookie HttpOnly, SameSite=Strict y Secure en producción.
- Expiración por inactividad y expiración absoluta.
- Vinculación moderada al agente de usuario.
- Revocación por versión de sesión y cierre de sesiones al cambiar la clave.
- No se utilizan localStorage ni sessionStorage para credenciales.

### Autorización

- Control de acceso del lado del servidor en cada ruta.
- Encargado de presupuesto: acceso a las tres áreas.
- Usuarios de Salud y Educación: aislamiento estricto de su área.
- La interfaz oculta funciones no permitidas, pero el servidor vuelve a validar siempre.

### CSRF y origen

- Token sincronizador CSRF por sesión para toda operación modificadora.
- Validación de `Origin` y `Referer` contra el origen configurado.
- SameSite=Strict como capa adicional.

### XSS

- Plantillas con autoescape.
- Escape explícito de contenido dinámico antes de usar HTML en el frontend.
- Content Security Policy sin scripts inline ni orígenes externos.
- Validación de tamaños y tipos de entrada.

### SQL Injection

- Consultas construidas con SQLAlchemy y parámetros enlazados.
- No se concatenan entradas del usuario para construir SQL.
- Privilegios de base de datos limitables a la aplicación.

### Clickjacking y navegación

- `frame-ancestors 'none'` en CSP.
- `X-Frame-Options: DENY`.
- `base-uri 'self'`, `form-action 'self'` y `object-src 'none'`.

### Carga de archivos

- Lista permitida de extensiones.
- Nombre de archivo reducido a su basename.
- Límite de bytes durante lectura incremental.
- Límite de filas y columnas.
- Control de expansión para archivos XLSX comprimidos.
- Procesamiento en memoria, sin ejecutar archivos ni construir rutas del sistema.
- Vista previa temporal asociada al usuario, área y año.

### HTTP y transporte

- HTTPS mediante Caddy en producción.
- HSTS en producción.
- `nosniff`, Referrer-Policy, Permissions-Policy, COOP y CORP.
- Respuestas privadas con `Cache-Control: no-store`.
- Cabecera Server deshabilitada en Uvicorn y removida en el proxy.

### Errores y observabilidad

- Errores internos registrados en servidor con request ID.
- El cliente recibe mensajes controlados sin stack traces.
- Logs estructurados JSON.
- Auditoría de usuario, fecha, IP, navegador, acción, entidad, resultado y contexto.

## Sobre la exposición del frontend

Un navegador necesariamente puede observar los archivos estáticos y las solicitudes de red que utiliza. Por eso no se utiliza ocultamiento de endpoints como control de seguridad. La solución minimiza los activos de producción, no publica mapas de fuente y no contiene secretos ni decisiones de autorización en el cliente. Toda operación relevante se verifica nuevamente en el servidor. La ofuscación puede dificultar una lectura casual, pero no reemplaza autenticación, autorización, validación y aislamiento.

## Credencial inicial solicitada

La clave `2026` se conserva únicamente para facilitar la migración inicial. Es una credencial débil y compartida. El despliegue productivo exige definir explícitamente una clave temporal y rotarla inmediatamente con `scripts/change_password.py`.

## Controles operativos requeridos antes de producción

- Administrar secretos fuera del repositorio.
- Restringir el acceso a PostgreSQL a la red interna.
- Aplicar actualizaciones de seguridad periódicas.
- Configurar copias de seguridad cifradas y probar restauraciones.
- Centralizar logs y alertas.
- Ejecutar análisis de dependencias, SAST, DAST y prueba de penetración.
- Definir retención de auditoría y protección de datos personales.
- Revisar TLS, DNS, firewall y permisos del host.
