# Actualización 2.1 — Usuarios y privilegios

## Funciones nuevas

- El inicio de sesión muestra los usuarios activos como una lista de selección única.
- El usuario solo debe seleccionar su nombre e ingresar su clave.
- El perfil con el privilegio **Administrar usuarios** dispone de un módulo para:
  - crear usuarios;
  - asignar una o más áreas: Municipal, Salud y Educación;
  - asignar privilegios específicos;
  - activar o desactivar cuentas;
  - modificar nombres, áreas y privilegios;
  - restablecer claves;
  - cerrar automáticamente sesiones anteriores cuando cambia una clave o autorización.
- Los permisos se validan tanto en la interfaz como en cada endpoint del servidor.
- Las acciones de administración de usuarios quedan registradas en auditoría.

## Privilegios disponibles

Los privilegios cubren requerimientos, presupuesto, reportes, respaldos, auditoría y administración de usuarios. El sistema agrega automáticamente dependencias indispensables; por ejemplo, editar un requerimiento requiere también visualizarlo y consultar el presupuesto.

## Seguridad

- Las claves continúan almacenándose con Argon2.
- El selector público solo entrega el nombre visible y un identificador opaco; no expone roles, áreas ni privilegios.
- Se conserva la protección de fuerza bruta por usuario seleccionado e IP.
- Al cambiar permisos, áreas, estado o clave, las sesiones afectadas se revocan.
- El administrador no puede desactivar su propia cuenta ni cambiar sus propias áreas o privilegios durante la sesión.

## Actualización sin perder datos

1. Desde la carpeta actual, ejecute `docker compose down`.
2. Reemplace los archivos del proyecto con esta versión, manteniendo el mismo nombre de carpeta.
3. Ejecute `docker compose up --build -d`.
4. La migración de base de datos se ejecuta automáticamente y conserva los presupuestos y requerimientos existentes.

No utilice `docker compose down -v`, porque elimina el volumen de PostgreSQL.
