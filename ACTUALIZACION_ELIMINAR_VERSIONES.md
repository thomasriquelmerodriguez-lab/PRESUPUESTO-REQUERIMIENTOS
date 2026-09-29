# Actualización: eliminar versiones de presupuesto

En **Actualizar presupuesto > Versiones disponibles** ahora aparece el botón **Eliminar versión** en cada versión, incluida la base incorporada.

## Comportamiento

- Una versión histórica se elimina sin modificar las demás.
- Si se elimina la versión activa, la versión anterior más reciente del mismo año se activa automáticamente.
- Si se elimina la única versión activa y no existe otra, el año queda creado pero **sin presupuesto activo**.
- También es posible eliminar la versión base incorporada. Si se elimina, deja de estar disponible la opción **Restaurar base** para esa versión.
- La eliminación queda registrada en auditoría.
- El presupuesto base eliminado no se recrea automáticamente en un despliegue posterior si el año presupuestario ya existía.

La acción requiere el permiso `budgets.import` y siempre solicita confirmación en la interfaz.
