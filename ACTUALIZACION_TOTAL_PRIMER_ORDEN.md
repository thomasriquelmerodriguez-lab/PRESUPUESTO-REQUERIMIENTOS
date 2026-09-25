# Actualización: presupuesto total por primer orden jerárquico

El presupuesto total de una planilla se calcula **únicamente** sumando las cuentas de primer orden estructural.

Ejemplo:

- `215-22-00-000-000-000` → Orden 1 → **sí suma al presupuesto total**.
- `215-22-01-000-000-000` → Orden 2 → no suma al total general.
- `215-22-01-001-000-000` → Orden 3 → no suma al total general.
- `215-22-01-002-000-000` → Orden 3 → no suma al total general.

Las cuentas de órdenes inferiores continúan visibles y disponibles para requerimientos, CAS y análisis por cuenta, pero no duplican el presupuesto total.

La vista previa de importación ahora muestra el número de cuentas de primer orden detectadas y el orden jerárquico de cada fila.
