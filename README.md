# Sistema profesional de requerimientos presupuestarios

Aplicación web multiusuario para administrar requerimientos y presupuestos de las áreas **Municipal, Salud y Educación**. Esta versión reemplaza la aplicación HTML local por una solución cliente-servidor con base de datos, autenticación, autorización, auditoría, control de concurrencia y despliegue mediante contenedores.

## Funcionalidad conservada

- Registro, consulta, edición y eliminación lógica de requerimientos.
- Fecha, expediente, materia, monto, departamento, área de gestión, observaciones y cuenta presupuestaria.
- Presupuesto separado por área y año.
- Jerarquía de cuentas y subasignaciones, incluyendo los niveles requeridos para 215-22, 215-24 y 215-31.
- Presupuesto vigente, nuevos requerimientos, Obligado CAS y disponible proyectado.
- Edición de Obligado CAS únicamente después de seleccionar la cuenta.
- Filtros por año, cuenta matriz, cuenta específica y texto.
- Reportes consolidados por cuenta matriz, imprimibles o guardables como PDF.
- Exportaciones CSV, respaldos JSON e importación de presupuestos Excel/CSV.
- Carga inicial de 655 requerimientos municipales 2026 y 180 cuentas presupuestarias.
- Usuarios y permisos para Encargado de presupuesto, Salud y Educación.
- Logo institucional y diseño responsive.

## Arquitectura

- **Backend:** Python 3.12, FastAPI y SQLAlchemy.
- **Base de datos:** PostgreSQL para producción; SQLite para pruebas y desarrollo sin contenedores.
- **Frontend:** HTML semántico, CSS Mobile First y JavaScript ES Modules sin frameworks pesados.
- **Proxy/TLS:** Caddy en el despliegue de producción.
- **Migraciones:** Alembic.
- **Contenedores:** Docker Compose.

La lógica crítica, los permisos, las validaciones, los cálculos presupuestarios y el control de concurrencia se ejecutan en el servidor. El navegador solo presenta información y solicita operaciones autorizadas.

## Inicio rápido con Docker

1. Instale Docker Desktop o Docker Engine con Docker Compose.
2. Copie `.env.example` a `.env` y cambie las claves.
3. Ejecute:

```bash
docker compose up --build -d
```

4. Abra `http://localhost:8000`.

En Windows también puede ejecutar `INICIAR_EN_WINDOWS.bat`. En Linux o macOS use `./INICIAR_EN_LINUX_MAC.sh`.

## Usuarios iniciales

- `Encargado de presupuesto`
- `Salud`
- `Educación`

La clave inicial solicitada para la migración es `2026`. **No debe mantenerse en producción.** Antes de habilitar acceso real, cambie cada clave con:

```bash
docker compose exec app python scripts/change_password.py "encargado de presupuesto"
docker compose exec app python scripts/change_password.py salud
docker compose exec app python scripts/change_password.py educacion
```

Para crear usuarios adicionales:

```bash
docker compose exec app python scripts/create_user.py usuario1 \
  --name "Usuario Salud 1" --role area_user --areas salud
```

## Producción

Consulte `docs/DESPLIEGUE_PRODUCCION.md`. El despliegue productivo exige HTTPS, secretos robustos y PostgreSQL. La documentación OpenAPI se desactiva automáticamente en producción.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest
```

La entrega incluye pruebas de datos migrados, aislamiento por área, CSRF, concurrencia optimista, cabeceras de seguridad, cookies de sesión, lista permitida de archivos y tratamiento parametrizado de búsquedas.

## Documentación incluida

- `docs/ARQUITECTURA.md`
- `docs/SEGURIDAD.md`
- `docs/AUDITORIA_Y_RIESGOS.md`
- `docs/MIGRACION_DATOS.md`
- `docs/DESPLIEGUE_PRODUCCION.md`
- `docs/PLAN_PRUEBAS.md`
- `CHANGELOG.md`

## Advertencia profesional

Ninguna aplicación puede declararse invulnerable únicamente por una refactorización de código. La seguridad final depende también de la configuración del servidor, gestión de secretos, actualizaciones, copias de seguridad, monitoreo, revisiones periódicas, pruebas de penetración y procedimientos operativos. Este proyecto aplica defensa en profundidad y queda preparado para una evaluación de seguridad previa a su puesta en producción.

## Administración de usuarios y privilegios

La versión 2.1 incorpora el módulo **Usuarios y privilegios**, visible para quienes tengan el permiso `users.manage`. Desde allí se pueden crear cuentas, asignar áreas, definir permisos, activar o desactivar usuarios y restablecer claves.

El inicio de sesión presenta una lista de usuarios activos. La persona selecciona su nombre e ingresa solamente su clave. La lista pública no entrega roles, áreas ni privilegios.

### Actualizar una instalación existente

Desde la carpeta de la aplicación:

```powershell
docker compose down
```

Reemplace los archivos por los de esta versión y ejecute:

```powershell
docker compose up --build -d
```

La migración se aplica automáticamente y conserva el volumen de PostgreSQL. No use `docker compose down -v`.


## Años presupuestarios configurables (v2.3.0)

El módulo **Actualizar presupuesto** permite crear nuevos años por área antes de cargar su planilla. Los años se mantienen separados por Municipal, Salud y Educación y pueden agregarse sin modificar código ni reinicializar la base de datos. Consulte `ACTUALIZACION_ANOS_PRESUPUESTARIOS.md` para el procedimiento de actualización y uso.

## Actualización de jerarquía presupuestaria

La carga de presupuesto reconoce filas de resumen y detalle por código. Consulte `ACTUALIZACION_JERARQUIA_PRESUPUESTARIA.md` para la regla aplicada y el procedimiento de despliegue en Render.
