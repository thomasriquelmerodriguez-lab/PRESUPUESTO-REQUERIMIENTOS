# Migración y compatibilidad de datos

## Datos incorporados

La semilla inicial conserva:

- 655 requerimientos del área Municipal para 2026.
- Monto total migrado: $2.522.408.220.
- 180 cuentas presupuestarias con presupuesto vigente mayor a cero.
- Nuevos requerimientos provenientes de PRE OBLIGADO ZE COMPRAS.
- Obligado CAS asociado a cada cuenta.
- Fecha, expediente, materia, monto total, departamento, área de gestión, observaciones y cuenta.

Los archivos normalizados se encuentran en:

- `data/seed/accounts_municipal_2026.json`
- `data/seed/requirements_municipal_2026.json`

## Correcciones controladas

- Fechas vacías se asignaron al 01-01-2026 para evitar registros sin fecha.
- Una fecha inexistente, 31-06-2026, se normalizó al último día válido de junio.
- Los datos originales se conservan mediante identificadores heredados y metadatos de origen.

## Compatibilidad futura

- Salud y Educación inician sin presupuesto y pueden cargar su propia planilla.
- Cada área puede mantener varios años, incluido 2027.
- Cada nueva carga crea una versión histórica y deja una sola versión activa por área y año.
- Los respaldos JSON de esta versión incluyen área, presupuestos y requerimientos.
- La importación de presupuestos reconoce CUENTA, DENOMINACIÓN, PRESUPUESTO VIGENTE, PRE OBLIGADO ZE COMPRAS/NUEVOS REQUERIMIENTOS y OBLIGADO CAS.

## Recomendación de migración productiva

1. Crear un respaldo de la aplicación anterior y de las planillas fuente.
2. Desplegar el nuevo sistema en un entorno de prueba.
3. Validar totales por área, año y cuenta matriz.
4. Revisar una muestra de expedientes contra la planilla original.
5. Rotar las claves iniciales.
6. Realizar una copia PostgreSQL antes de habilitar usuarios.
7. Definir una fecha de corte y evitar doble ingreso entre ambos sistemas.
