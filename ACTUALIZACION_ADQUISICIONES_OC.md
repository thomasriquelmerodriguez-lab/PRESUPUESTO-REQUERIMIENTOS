# Actualización: Adquisiciones, Órdenes de Compra y conciliación CAS

## Objetivo

La aplicación distingue ahora entre el **monto solicitado originalmente** y el **monto realmente adjudicado**. El propósito es que un requerimiento no mantenga comprometido un monto mayor cuando la compra finalmente se adjudica por menos.

Ejemplo:

- Requerimiento: $10.000.000
- Orden de compra: $7.000.000
- Si el proceso sigue abierto: se mantienen $7.000.000 de OC + $3.000.000 de reserva = $10.000.000 comprometidos.
- Si el proceso se cierra: se liberan $3.000.000 y quedan $7.000.000 comprometidos.
- Cuando la OC ya está incluida en Obligado CAS y se marca como **conciliada**, deja de descontarse separadamente. El gasto queda representado por CAS y no se duplica.

## Nuevo módulo

Se agregó **Adquisiciones / OC** al menú principal. Los usuarios pueden recibir dos permisos:

- `acquisitions.view`: consultar procesos y órdenes de compra.
- `acquisitions.manage`: modificar etapas, registrar/editar/eliminar OC, cerrar requerimientos y conciliar con CAS.

El Encargado de Presupuesto recibe ambos permisos automáticamente mediante la migración. Los demás usuarios pueden configurarse desde **Usuarios y privilegios**.

## Etapas disponibles

1. Registrado
2. En adquisiciones
3. En licitación
4. Adjudicado
5. OC emitida
6. Cerrado

## Fórmula de compromiso

Para cada requerimiento:

**Reserva pendiente = 0 si está cerrado; en caso contrario, máximo(Solicitado − total OC, 0)**

**Compromiso req./OC = Reserva pendiente + OC no conciliadas con CAS**

El saldo por cuenta se calcula como:

**Saldo real = Presupuesto vigente − Compromiso req./OC − Obligado CAS**

Esto evita doble descuento cuando una OC ya pasó a Obligado CAS.

## Dashboard

El Dashboard incorpora:

- Solicitado original.
- Órdenes de compra emitidas.
- Saldo liberado por adjudicaciones menores.
- Compromiso req./OC vigente.
- Obligado CAS.
- Saldo real disponible.
- Comparación mensual entre monto solicitado y OC emitidas.

## Respaldos

El formato de respaldo se actualizó a versión 3 e incluye:

- Estado de adquisiciones de cada requerimiento.
- Estado de cierre.
- Órdenes de compra.
- Conciliación con CAS.

La importación sigue aceptando respaldos v1 y v2.

## Actualización en Render

1. Reemplace en GitHub los archivos del proyecto por esta versión.
2. No modifique `DATABASE_URL`, `APP_ORIGIN` ni `SECRET_KEY`.
3. En Render ejecute **Manual Deploy → Deploy latest commit**.
4. Alembic aplicará la migración `9e0f2a4b6c7d` y conservará los datos existentes.
5. Cierre sesión y vuelva a ingresar para que el Encargado de Presupuesto reciba los nuevos permisos en la sesión.

## Vista previa

Abra `VISTA_PREVIA_ADQUISICIONES.html` para ver una simulación del módulo con el ejemplo de $10.000.000 solicitado y $7.000.000 adjudicado.
