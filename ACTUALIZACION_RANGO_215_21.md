# Actualización: rango presupuestario desde 215-21

La carga de presupuestos ahora considera exclusivamente las cuentas de gasto desde la cuenta **215-21** en adelante.

## Regla aplicada

- Se excluyen del presupuesto las cuentas anteriores a `215-21`.
- Se excluyen otras clases contables completas, por ejemplo cuentas `115-...`.
- Se incluyen `215-21`, `215-22`, `215-23`, `215-24`, `215-25`, `215-26`, `215-29`, `215-31`, `215-33` y cualquier ítem posterior dentro de la clase 215.
- También se mantienen compatibles planillas antiguas que omiten el prefijo `215` y usan códigos como `21-00-...` o `22-01-...`.
- El presupuesto total se calcula sumando únicamente las cuentas estructurales de **primer orden** dentro de este rango, por ejemplo `215-21-00-000-000-000` y `215-22-00-000-000-000`.
- Los niveles inferiores se mantienen en el catálogo para desglose, requerimientos y Obligado CAS, sin duplicar el total general.

## Ejemplo

Si una planilla contiene:

- `215-20-00-000-000-000` = $9.000.000 → excluida
- `215-21-00-000-000-000` = $1.000.000 → incluida en el total
- `215-22-00-000-000-000` = $2.000.000 → incluida en el total
- `215-22-01-000-000-000` = $500.000 → detalle, no vuelve a sumarse
- `115-03-00-000-000-000` = $8.000.000 → excluida

El presupuesto general será **$3.000.000**.

Para que una versión ya cargada use esta regla, vuelva a cargar la planilla después de desplegar esta actualización.
