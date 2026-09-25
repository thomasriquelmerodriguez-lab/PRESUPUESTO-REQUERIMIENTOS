# Publicación del Sistema de Requerimientos en Internet

Esta edición está preparada para funcionar como una aplicación web multiusuario en un VPS con Docker y dominio propio.

## 1. Tipo de hosting necesario

Use un **VPS Linux** donde tenga acceso SSH/root y pueda instalar Docker. Un hosting que solo permita subir HTML/PHP por FTP no es suficiente para esta aplicación, porque el sistema utiliza FastAPI, PostgreSQL, sesiones de servidor y procesos de migración.

Configuración inicial razonable para uso municipal: 2 vCPU, 4 GB RAM, 40 GB SSD o superior, Ubuntu LTS, IP pública fija y copias de seguridad del proveedor.

## 2. Dominio

Cree un subdominio, por ejemplo:

`presupuesto.municipalidad.cl`

En el proveedor DNS, agregue un registro **A** apuntando ese nombre a la IP pública del VPS. Espere la propagación antes de solicitar HTTPS.

## 3. Copiar el proyecto al VPS

Puede usar SFTP, SCP o el administrador de archivos que entregue el VPS. Deje el proyecto, por ejemplo, en:

`/opt/sistema-requerimientos`

No suba el archivo `.env` de su computador. Genere uno nuevo en el servidor.

## 4. Preparar Ubuntu

Desde SSH:

```bash
cd /opt/sistema-requerimientos
sudo bash scripts/online/instalar_vps_ubuntu.sh
```

Luego genere los secretos:

```bash
python3 scripts/online/generar_env.py
```

El asistente pedirá el dominio y una clave inicial temporal. Los secretos se generan aleatoriamente.

## 5. Iniciar el sitio

```bash
bash scripts/online/iniciar_online.sh
```

Caddy obtiene y renueva automáticamente el certificado HTTPS cuando el dominio apunta correctamente al VPS y los puertos 80/443 están accesibles.

Compruebe:

```bash
docker compose --env-file .env -f docker-compose.online.yml ps
```

Abra en un navegador:

`https://SU_DOMINIO`

## 6. Llevar los datos que ya tiene en su PC

### En Windows

En la carpeta de la aplicación local actual ejecute:

`EXPORTAR_BASE_LOCAL_WINDOWS.bat`

Puede copiar este archivo desde `scripts/online/EXPORTAR_BASE_LOCAL_WINDOWS.bat` a la carpeta de la instalación actual antes de ejecutarlo. Se generará un archivo `.dump`.

Suba ese `.dump` al VPS, por ejemplo a `/opt/sistema-requerimientos/backups/`.

### En el VPS

Antes de restaurar, confirme que el sistema online inició al menos una vez. Luego:

```bash
bash scripts/online/restaurar.sh backups/presupuesto_local_XXXXXXXX.dump
```

La restauración reemplaza los datos vacíos/iniciales del servidor por los datos de su computador: usuarios, presupuestos, requerimientos, Obligado CAS, años y permisos.

## 7. Respaldos

Ejecute periódicamente:

```bash
bash scripts/online/backup.sh
```

Los archivos se guardan en `backups/`. Una copia debe almacenarse fuera del VPS (otro servidor, almacenamiento corporativo cifrado, etc.).

## 8. Actualizaciones futuras

Antes de actualizar:

```bash
bash scripts/online/backup.sh
```

Después de reemplazar el código por una versión nueva, conserve el mismo `.env` y ejecute:

```bash
bash scripts/online/actualizar_online.sh
```

Las migraciones de base de datos se aplican al iniciar el contenedor.

## 9. Seguridad mínima antes de uso real

- Cambie cualquier contraseña temporal o de prueba.
- No publique `.env` ni archivos `.dump` en una carpeta web.
- Mantenga Ubuntu y Docker actualizados.
- Mantenga abiertos públicamente solo SSH, 80 y 443; PostgreSQL no se publica al exterior.
- Restrinja SSH preferentemente con claves y deshabilite autenticación root por contraseña cuando el VPS esté configurado.
- Active copias automáticas del VPS además del respaldo de PostgreSQL.
- Revise los registros de auditoría y de intentos de inicio de sesión.
- Para información municipal sensible, evalúe políticas institucionales sobre alojamiento, residencia de datos, respaldos y acceso administrativo antes de producción.

## 10. Arquitectura online

Navegador -> HTTPS/Caddy -> FastAPI -> PostgreSQL

PostgreSQL está en una red Docker interna y no tiene puerto público. Caddy es el único componente expuesto en 80/443.
