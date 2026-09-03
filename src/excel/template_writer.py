"""Escribe valores de indicadores en una copia de la plantilla Excel de una institución.

Nunca modifica el archivo plantilla original (decisión 4 del prompt): primero
se copia el archivo a la ruta de salida, y recién ahí se abre la copia con
openpyxl para escribir encima.

No hace falta la contraseña de protección de hoja para escribir: se verificó
en la Fase 0, contra la plantilla real convertida, que openpyxl escribe
valores en una hoja protegida sin pedirla, y que el archivo resultante
conserva la protección, el ``number_format`` original de cada celda y las
celdas combinadas intactas. Los tests de este módulo repiten esa
verificación contra un fixture sintético (no el archivo real de producción).
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import openpyxl

logger = logging.getLogger(__name__)


class TemplateWriterError(ValueError):
    """Error al escribir la plantilla (falta el archivo, falta la hoja, etc.)."""


def write_values(
    template_path: str | Path,
    output_path: str | Path,
    hoja: str,
    values: dict[str, float | None],
) -> Path:
    """Copia ``template_path`` a ``output_path`` y escribe ``values`` en ``hoja``.

    ``values`` es {celda: valor}, ej. {"G22": 346.34, "W45": None}. Un valor
    None se escribe tal cual (celda vacía): decidir qué hacer con los
    indicadores sin resultado es responsabilidad del log de control (Fase 4),
    no de este módulo.

    Devuelve ``output_path``. Si ya existe, se sobreescribe (volver a correr
    una exportación para la misma institución/mes es un caso de uso normal,
    no un error), pero se deja constancia en el log.
    """
    template_path = Path(template_path)
    output_path = Path(output_path)

    if not template_path.exists():
        raise TemplateWriterError(f"no existe la plantilla {template_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        logger.info("%s ya existía, se sobreescribe", output_path)
    shutil.copy2(template_path, output_path)

    wb = openpyxl.load_workbook(output_path)
    if hoja not in wb.sheetnames:
        raise TemplateWriterError(
            f"la plantilla {template_path} no tiene una hoja llamada {hoja!r} "
            f"(hojas disponibles: {wb.sheetnames})"
        )
    sheet = wb[hoja]

    for celda, valor in values.items():
        sheet[celda] = valor

    wb.save(output_path)
    return output_path
