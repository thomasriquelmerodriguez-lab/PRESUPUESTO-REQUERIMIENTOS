# Actualización: reemplazo total del presupuesto y eliminación visible

## Qué corrige

1. Una nueva planilla para un área/año pasa a ser el presupuesto vigente completo.
   - No se suma con la versión anterior.
   - Las cuentas presentes reemplazan sus valores anteriores.
   - Las cuentas nuevas se incorporan.
   - Las cuentas que no estén en la nueva planilla dejan de formar parte de la versión activa.
   - La versión anterior se conserva en el historial hasta que el usuario decida eliminarla.

2. El total general se calcula exclusivamente con cuentas de primer orden jerárquico.

3. El Obligado CAS se conserva por el mismo código cuando la planilla nueva no incluye columna CAS.

4. Se corrige el caché del navegador en Render. Los archivos JS/CSS dejan de reutilizar versiones antiguas durante una actualización, lo que podía ocultar el botón "Eliminar versión" o ejecutar una lógica de importación anterior.

5. En "Versiones disponibles" cada versión muestra "Eliminar versión" para usuarios con privilegio `budgets.import`.

## Despliegue Render

Reemplazar el repositorio por esta versión y ejecutar Manual Deploy -> Deploy latest commit. No modificar PostgreSQL ni las variables de entorno.
