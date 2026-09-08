"""Carga y validación de config/indicator_map.csv (indicador -> celda)."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

CELL_PATTERN = re.compile(r"^[A-Z]+[0-9]+$")

REQUIRED_COLUMNS = ("plasqlid", "institucion_id", "hoja", "celda")


class IndicatorMapError(ValueError):
    """Error de validación de config/indicator_map.csv."""


@dataclass(frozen=True)
class IndicatorMapEntry:
    plasqlid: int
    institucion_id: str
    hoja: str
    celda: str


def load_indicator_map(path: str | Path) -> list[IndicatorMapEntry]:
    """Carga y valida un archivo indicator_map.csv.

    Columnas requeridas: plasqlid, institucion_id, hoja, celda.

    Falla con IndicatorMapError si:
    - falta alguna columna requerida en el encabezado,
    - a alguna fila le falta un valor obligatorio,
    - una celda no tiene formato de celda de Excel (ej. "G22"),
    - un mismo plasqlid, para la misma institución, aparece mapeado a más de
      una celda distinta (ambiguo: no se sabe cuál usar).

    Un CSV con encabezado pero sin filas de datos no es un error: devuelve
    una lista vacía y deja una advertencia en el log, para que quede
    señalado sin frenar el programa.
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise IndicatorMapError(f"{path}: el CSV no tiene encabezado")
        missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
        if missing:
            raise IndicatorMapError(
                f"{path}: faltan columnas requeridas {missing} "
                f"en el encabezado {reader.fieldnames}"
            )
        rows = list(reader)

    if not rows:
        logger.warning("%s: el mapa de indicadores no tiene filas de datos", path)
        return []

    entries: list[IndicatorMapEntry] = []
    seen: dict[tuple[str, int], str] = {}

    for line_no, row in enumerate(rows, start=2):  # fila 1 = encabezado
        raw_id = (row.get("plasqlid") or "").strip()
        institucion_id = (row.get("institucion_id") or "").strip()
        # OJO: "hoja" no se recorta. Algunos nombres de hoja reales tienen un
        # espacio final legítimo (ej. "4315 Utilizacion "); recortarlo hace
        # que después no matchee contra wb.sheetnames al escribir.
        hoja = row.get("hoja") or ""
        celda = (row.get("celda") or "").strip()

        if not raw_id:
            raise IndicatorMapError(f"{path}:{line_no}: falta plasqlid")
        try:
            plasqlid = int(raw_id)
        except ValueError as exc:
            raise IndicatorMapError(
                f"{path}:{line_no}: plasqlid {raw_id!r} no es un entero válido"
            ) from exc

        if not institucion_id:
            raise IndicatorMapError(f"{path}:{line_no}: falta institucion_id")
        if not hoja.strip():
            raise IndicatorMapError(f"{path}:{line_no}: falta hoja")
        if not CELL_PATTERN.match(celda):
            raise IndicatorMapError(
                f"{path}:{line_no}: celda {celda!r} no tiene formato válido "
                f"(se esperaba algo como 'G22')"
            )

        key = (institucion_id, plasqlid)
        if key in seen and seen[key] != celda:
            raise IndicatorMapError(
                f"{path}:{line_no}: plasqlid {plasqlid} para institución "
                f"{institucion_id!r} ya está mapeado a la celda {seen[key]!r}, "
                f"no puede apuntar también a {celda!r}"
            )
        seen[key] = celda

        entries.append(
            IndicatorMapEntry(
                plasqlid=plasqlid,
                institucion_id=institucion_id,
                hoja=hoja,
                celda=celda,
            )
        )

    return entries
