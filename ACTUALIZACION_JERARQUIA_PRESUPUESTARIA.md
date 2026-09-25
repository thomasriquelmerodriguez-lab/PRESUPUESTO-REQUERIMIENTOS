# Actualización: jerarquía presupuestaria

Esta versión corrige el cálculo de presupuestos cuando la planilla contiene filas de resumen, subtotales y detalle.

## Regla aplicada

Las cuentas se organizan según el código y solo las raíces de cada rama se usan para calcular el presupuesto total. Los hijos se conservan para consulta, requerimientos y saldos, pero no vuelven a sumarse al total general.

Ejemplo:

- `22-00-000-000-000` — nivel 0 / cuenta matriz
  - `22-01-000-000-000` — nivel 1
    - `22-01-001-000-000` — nivel 2
    - `22-01-002-000-000` — nivel 2

Si `22-00-000-000-000` contiene el total de la rama, el sistema no suma adicionalmente `22-01`, `22-01-001` y `22-01-002` al total general.

La misma regla funciona con el formato completo, por ejemplo `215-22-00-000-000-000`.

## Compatibilidad

Si una planilla antigua no contiene una fila de resumen superior, la cuenta existente más cercana se considera raíz. Esto evita romper los presupuestos anteriores.

## Cambios incluidos

- Jerarquía calculada usando todas las cuentas presentes en la planilla.
- Padre, nivel y cuenta matriz determinados por los códigos realmente cargados.
- Presupuesto total calculado solo con cuentas raíz.
- Pre obligado y Obligado CAS de la vista previa calculados sin duplicar montos repetidos entre padres e hijos.
- Filtros de requerimientos asociados a la matriz real almacenada en el presupuesto.
- Migración automática que recalcula la jerarquía de los presupuestos ya cargados y corrige su total vigente.
- Plantilla CSV actualizada con un ejemplo jerárquico.

## Render

Al desplegar esta versión, Alembic ejecutará automáticamente la migración:

`4a6b8c0d2e3f -> 5b7c9d1e3f4a`

No es necesario borrar la base de datos ni volver a crear usuarios. El presupuesto que ya fue cargado en Render será recalculado automáticamente.
