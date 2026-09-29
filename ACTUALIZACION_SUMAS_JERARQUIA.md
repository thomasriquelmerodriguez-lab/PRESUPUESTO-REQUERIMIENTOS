# Actualización: suma de presupuesto por niveles jerárquicos

Fecha: 29-09-2026

## Regla aplicada

Al cargar o actualizar una planilla presupuestaria, los montos se recalculan desde el nivel más profundo hacia arriba.

Ejemplo:

- `215-22-01-001-000-000` = monto cargado de la cuenta detalle.
- `215-22-01-002-000-000` = monto cargado de la cuenta detalle.
- `215-22-01-000-000-000` = suma de `215-22-01-001...` + `215-22-01-002...`.
- `215-22-00-000-000-000` = suma de todas sus cuentas hijas de segundo orden.

Si una cuenta tiene hijos, el monto del padre se obtiene de la suma de esos hijos. El valor que pudiera venir escrito en la fila padre de la planilla no se vuelve a sumar.

El presupuesto total general continúa siendo la suma exclusiva de las cuentas estructurales de primer orden, por ejemplo:

- `215-21-00-000-000-000`
- `215-22-00-000-000-000`
- `215-24-00-000-000-000`
- `215-31-00-000-000-000`

De esta manera no existe doble contabilización entre niveles.

## Vista previa

La vista previa de importación ahora distingue entre:

- monto cargado originalmente en la planilla;
- presupuesto calculado por jerarquía;
- orden jerárquico de cada cuenta.

## Presupuestos ya cargados

La migración `7d9e1f3a5b6c` recalcula los presupuestos históricos que contienen la jerarquía necesaria. En versiones antiguas sin cuentas de primer orden completas, el total general previo se conserva para evitar reemplazarlo por cero.

## Validación

Se ejecutaron 26 pruebas automatizadas, incluyendo un caso donde los valores cargados en las cuentas padre son incorrectos y el sistema los reemplaza por la suma exacta de sus cuentas hijas.
