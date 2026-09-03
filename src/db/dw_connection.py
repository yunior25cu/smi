"""Conexión al data warehouse real, donde viven las tablas que consultan las
PLASQLSENT (dwfarrec, DWAfilia, DWTecOrd, clascat, etc.).

Confirmado con el usuario en la Fase 3: es una base **Oracle**, separada del
servidor SQL Server que solo tiene el catálogo (`MAGIK.PLACONSU`, ver
`src/db/connection.py`). Por decisión explícita del usuario, implementar este
conector se pospuso a propósito hasta el final del proyecto. Hasta entonces,
esta función falla con un mensaje claro en vez de dejar que el resto del
pipeline use una conexión equivocada o inventada.
"""

from __future__ import annotations


class DwConnectionNotConfiguredError(NotImplementedError):
    """El conector al data warehouse (Oracle) todavía no está implementado."""


def get_dw_connection():
    raise DwConnectionNotConfiguredError(
        "el conector al data warehouse (Oracle) todavía no está implementado: "
        "se dejó pospuesto a propósito hasta el final del proyecto (ver "
        "README, sección 'Pendiente de Fase 2'). run_export()/cli.py aceptan "
        "cualquier conexión DB-API 2.0 para dw_conn, así que una vez armado "
        "el conector Oracle no hace falta tocar el resto del pipeline."
    )
