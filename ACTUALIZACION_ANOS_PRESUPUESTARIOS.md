# Actualización: años presupuestarios configurables

## Qué cambia

La aplicación permite crear nuevos años presupuestarios directamente desde **Actualizar presupuesto**. Cada año se administra por separado para Municipal, Salud y Educación.

### Flujo de uso

1. Ingrese al área correspondiente.
2. Abra **Actualizar presupuesto**.
3. En **Años presupuestarios**, escriba el nuevo año (por ejemplo, 2027) y presione **Agregar año**.
4. El año aparecerá con estado **Sin presupuesto**.
5. Presione **Cargar presupuesto** o seleccione el año en **Cargar o actualizar presupuesto**.
6. Adjunte la planilla Excel o CSV.
7. Revise la vista previa y aplique el presupuesto.
8. Una vez aplicado, el año quedará disponible en Nuevo requerimiento, Presupuesto vigente y los filtros correspondientes.

## Permisos

- Para crear años y cargar presupuestos se requiere el privilegio **Actualizar presupuesto** (`budgets.import`).
- El servidor valida también el acceso al área. Un usuario de Salud no puede crear o cargar años de Municipal o Educación.
- El Encargado de presupuesto puede hacerlo en las tres áreas si conserva esos privilegios.

## Compatibilidad con datos existentes

La migración `3f5a7c9d1e2b` crea la tabla de períodos presupuestarios y registra automáticamente todos los años que ya tengan versiones presupuestarias. El presupuesto municipal 2026, requerimientos, Obligado CAS, usuarios y permisos existentes se conservan.

## Actualización en Windows sin perder la base de datos

Desde la carpeta de la versión actualmente ejecutándose:

```powershell
docker compose down
```

No use `-v`.

Descomprima la nueva versión y, dentro de su carpeta, ejecute:

```powershell
docker compose up --build -d
```

La aplicación ejecutará automáticamente `alembic upgrade head` y reutilizará el volumen `sistema_requerimientos_profesional_postgres_data`.
