# Despliegue de producción

## Requisitos

- Servidor Linux actualizado.
- Docker Engine y Docker Compose.
- Dominio DNS apuntando al servidor.
- Puertos 80 y 443 disponibles.
- Política de copias de seguridad y monitoreo.

## Configuración

1. Copie `.env.production.example` a `.env`.
2. Genere secretos independientes:

```bash
python scripts/generate_secret.py
```

3. Complete dominio, origen HTTPS, clave PostgreSQL, SECRET_KEY y clave inicial temporal.
4. Ejecute:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Caddy solicitará y renovará certificados TLS automáticamente cuando el DNS y los puertos sean correctos.

## Migraciones y semilla

El contenedor ejecuta `alembic upgrade head` y luego la semilla idempotente antes de iniciar Uvicorn. En una plataforma con varias réplicas o despliegues orquestados, las migraciones deben ejecutarse como un trabajo único previo al despliegue. La semilla usa un bloqueo asesor de PostgreSQL para serializar su ejecución.

## Cambio inmediato de claves

```bash
docker compose -f docker-compose.prod.yml exec app \
  python scripts/change_password.py "encargado de presupuesto"
```

Repita para Salud y Educación. La operación incrementa la versión de sesión y cierra todas las sesiones anteriores.

## Copia de seguridad de PostgreSQL

Ejemplo de respaldo lógico:

```bash
docker compose -f docker-compose.prod.yml exec -T db \
  pg_dump -U presupuesto -d presupuesto -Fc > presupuesto_$(date +%F).dump
```

Ejemplo de restauración en un ambiente controlado:

```bash
cat presupuesto_2026-08-06.dump | docker compose -f docker-compose.prod.yml exec -T db \
  pg_restore -U presupuesto -d presupuesto --clean --if-exists
```

Pruebe periódicamente la restauración. Almacene copias cifradas fuera del servidor principal.

## Escalado

La aplicación puede utilizar varios workers contra PostgreSQL. Para múltiples contenedores o alta disponibilidad se recomienda incorporar Redis para sesiones/eventos, un balanceador, almacenamiento central de logs y un trabajo único de migraciones.

## Operación

- Revise `/health` mediante el sistema de monitoreo.
- Centralice los logs JSON de app, Caddy y PostgreSQL.
- Alerte ante errores 5xx, intentos de acceso fallidos y falta de espacio.
- Mantenga imágenes y dependencias actualizadas.
- No exponga directamente el puerto de PostgreSQL a internet.
