from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDefinition:
    code: str
    label: str
    description: str
    category: str


PERMISSION_DEFINITIONS: tuple[PermissionDefinition, ...] = (
    PermissionDefinition("requirements.view", "Visualizar requerimientos", "Consultar registros y sus detalles.", "Requerimientos"),
    PermissionDefinition("requirements.create", "Crear requerimientos", "Ingresar nuevos requerimientos presupuestarios.", "Requerimientos"),
    PermissionDefinition("requirements.edit", "Editar requerimientos", "Modificar registros y gestionar bloqueos de edición.", "Requerimientos"),
    PermissionDefinition("requirements.delete", "Eliminar requerimientos", "Eliminar lógicamente registros existentes.", "Requerimientos"),
    PermissionDefinition("requirements.export", "Exportar requerimientos", "Descargar listados de requerimientos en CSV.", "Requerimientos"),
    PermissionDefinition("budgets.view", "Visualizar presupuesto", "Consultar cuentas, saldos e indicadores presupuestarios.", "Presupuesto"),
    PermissionDefinition("budgets.edit_cas", "Modificar Obligado CAS", "Editar el monto de Obligado CAS por cuenta.", "Presupuesto"),
    PermissionDefinition("budgets.import", "Actualizar presupuesto", "Cargar, aplicar y restaurar planillas presupuestarias.", "Presupuesto"),
    PermissionDefinition("budgets.export", "Exportar presupuesto", "Descargar el catálogo presupuestario en CSV.", "Presupuesto"),
    PermissionDefinition("reports.generate", "Generar reportes", "Generar reportes consolidados por cuenta matriz.", "Reportes y respaldo"),
    PermissionDefinition("backups.export", "Descargar respaldos", "Exportar respaldos JSON del área autorizada.", "Reportes y respaldo"),
    PermissionDefinition("backups.import", "Restaurar respaldos", "Importar respaldos JSON en el área autorizada.", "Reportes y respaldo"),
    PermissionDefinition("audit.view", "Visualizar auditoría", "Consultar trazabilidad, direcciones IP y eventos de seguridad.", "Administración"),
    PermissionDefinition("users.manage", "Administrar usuarios", "Crear usuarios, asignar áreas, privilegios, claves y estado.", "Administración"),
)

PERMISSION_CODES = frozenset(item.code for item in PERMISSION_DEFINITIONS)

AREA_USER_DEFAULT_PERMISSIONS = frozenset(
    {
        "requirements.view",
        "requirements.create",
        "requirements.edit",
        "requirements.delete",
        "requirements.export",
        "budgets.view",
        "budgets.edit_cas",
        "budgets.import",
        "budgets.export",
        "reports.generate",
        "backups.export",
        "backups.import",
    }
)

MANAGER_DEFAULT_PERMISSIONS = PERMISSION_CODES
