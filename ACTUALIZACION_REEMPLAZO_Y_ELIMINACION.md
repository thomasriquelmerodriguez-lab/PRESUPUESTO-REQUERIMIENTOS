# Actualización: reemplazo de presupuesto y eliminación de cargas

## 1. Nueva regla al actualizar un presupuesto

Una carga nueva **no se suma** al presupuesto anterior.

La actualización se realiza por **código de cuenta**:

- Si la cuenta ya existe, el valor de la nueva planilla **reemplaza** el valor anterior.
- Si la cuenta no existe, se incorpora como **cuenta nueva**.
- Si una cuenta anterior no aparece en la nueva planilla, se conserva sin cambios.
- El total vigente se recalcula desde las cuentas de **primer orden jerárquico** del presupuesto resultante.
- Los valores de Obligado CAS existentes se conservan cuando la nueva planilla no incluye la columna OBLIGADO CAS.

### Ejemplo

Presupuesto vigente:

- `215-22-00-000-000-000 = $100`

Nueva planilla:

- `215-22-00-000-000-000 = $120`

Resultado:

- Presupuesto vigente = **$120**
- No se calcula `$100 + $120`.

La vista previa muestra ahora:

- presupuesto anterior;
- nuevo presupuesto vigente;
- cuentas modificadas;
- cuentas nuevas;
- cuentas anteriores que se conservan.

## 2. Jerarquía

La jerarquía se utiliza para ordenar las cuentas, determinar padre/hijo y calcular el total general exclusivamente desde las cuentas de primer orden.

Los montos cargados para cada cuenta son los valores vigentes de esa cuenta y **no se reemplazan automáticamente por la suma de sus hijos**.

## 3. Eliminar presupuestos cargados

En el historial de presupuestos aparece el botón **Eliminar presupuesto** para las versiones cargadas por usuario.

- Una versión histórica puede eliminarse directamente.
- Si se elimina la versión vigente, el sistema restaura automáticamente la versión anterior disponible.
- La base incorporada del sistema no se puede eliminar; se mantiene como mecanismo de recuperación.

La eliminación queda registrada en auditoría.

## 4. Render

Esta actualización no cambia las variables de entorno ni la estructura de PostgreSQL. No requiere una migración adicional.

Para instalarla:

1. Reemplazar los archivos del repositorio GitHub por los de esta versión.
2. Confirmar los cambios en `main`.
3. En Render ejecutar **Manual Deploy -> Deploy latest commit**.
4. Una vez desplegada, volver a cargar la planilla de presupuesto vigente para que sus valores queden como referencia actual.

## Verificación

Se ejecutaron 28 pruebas automatizadas, incluyendo:

- reemplazo `$100 -> $120` sin suma acumulativa;
- incorporación de una cuenta nueva;
- conservación de cuentas no incluidas en una actualización parcial;
- conservación de Obligado CAS cuando la columna no viene en la planilla;
- eliminación de la versión vigente y restauración automática de la anterior.
