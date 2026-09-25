# Actualización: presupuesto dinámico

## Nueva fórmula

**Disponible = Presupuesto vigente - Requerimientos ingresados - Obligado CAS**

### Requerimientos
Los requerimientos activos registrados en la aplicación son la fuente de verdad. Al crear, editar o eliminar un requerimiento, el disponible se recalcula automáticamente. Los 655 requerimientos municipales 2026 ya migrados también participan del cálculo.

### PRE OBLIGADO
El valor PRE OBLIGADO proveniente de planillas anteriores se conserva únicamente como referencia de importación y respaldo. No se vuelve a descontar, evitando que un mismo requerimiento se rebaje dos veces.

### Obligado CAS
La actualización incluye una migración de datos que recupera los valores no cero de Obligado CAS de la planilla municipal 2026 anterior y los incorpora en las cuentas correspondientes. La edición manual de Obligado CAS continúa disponible según los permisos del usuario.

## Actualización sobre una instalación existente
1. Realizar un respaldo desde la aplicación.
2. En PowerShell, dentro de la carpeta actual, ejecutar `docker compose down`. No usar `-v`.
3. Descomprimir esta versión.
4. Abrir PowerShell en la nueva carpeta y ejecutar `docker compose up --build -d`.
5. La migración se ejecuta automáticamente al iniciar el contenedor.

El nombre del proyecto Docker se mantiene, por lo que reutiliza el volumen PostgreSQL existente y conserva usuarios, requerimientos y presupuestos.
