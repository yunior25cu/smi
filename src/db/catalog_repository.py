"""Acceso al catálogo de indicadores MAGIK.PLACONSU.

Hallazgo de la Fase 0: PLACONSU no tiene columna de institución (cada base
pertenece a una sola institución) y tiene filas con PLASQLID duplicado —
2248 valores distintos de PLASQLID en 4496 filas, cada uno repetido
exactamente una vez con contenido idéntico. Este módulo colapsa esos
duplicados idénticos y falla explícitamente si encuentra un PLASQLID
duplicado con contenido *distinto* (no hay forma automática de saber cuál
versión es la correcta).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable

logger = logging.getLogger(__name__)

CATALOG_QUERY = "SELECT PLASQLID, PLASQLNOM, PLASQLDESC, PLASQLSENT FROM PLACONSU"


class CatalogError(ValueError):
    """Error al leer o interpretar el catálogo PLACONSU."""


@dataclass(frozen=True)
class CatalogEntry:
    plasqlid: int
    nombre: str
    descripcion: str
    sentencia: str


def fetch_catalog(conn) -> list[CatalogEntry]:
    """Trae el catálogo completo de PLACONSU y lo valida/deduplica.

    ``conn`` es una conexión DB-API 2.0 (ej. pyodbc.Connection) ya abierta.
    """
    cursor = conn.cursor()
    cursor.execute(CATALOG_QUERY)
    rows = cursor.fetchall()
    return build_catalog(rows)


def build_catalog(rows: Iterable[Any]) -> list[CatalogEntry]:
    """Convierte filas crudas (PLASQLID, PLASQLNOM, PLASQLDESC, PLASQLSENT)
    en una lista de CatalogEntry validada y deduplicada.

    Separado de fetch_catalog para poder testearlo sin una conexión real.
    """
    by_id: dict[int, CatalogEntry] = {}
    duplicates_collapsed = 0

    for row in rows:
        raw_id, nombre, descripcion, sentencia = row[0], row[1], row[2], row[3]
        plasqlid = _to_int_id(raw_id)

        if sentencia is None or not str(sentencia).strip():
            raise CatalogError(f"plasqlid {plasqlid}: PLASQLSENT vacío en el catálogo")

        entry = CatalogEntry(
            plasqlid=plasqlid,
            nombre=(nombre or "").strip(),
            descripcion=(descripcion or "").strip(),
            sentencia=str(sentencia),
        )

        existing = by_id.get(plasqlid)
        if existing is not None:
            if existing == entry:
                duplicates_collapsed += 1
                continue
            raise CatalogError(
                f"plasqlid {plasqlid} aparece más de una vez en PLACONSU con "
                f"contenido distinto (nombre, descripción o sentencia no "
                f"coinciden); no se puede elegir automáticamente cuál versión "
                f"es la correcta"
            )
        by_id[plasqlid] = entry

    if duplicates_collapsed:
        logger.warning(
            "PLACONSU tiene %d fila(s) duplicada(s) exactas que se "
            "colapsaron a una sola por plasqlid",
            duplicates_collapsed,
        )

    return sorted(by_id.values(), key=lambda e: e.plasqlid)


def _to_int_id(raw_id: Any) -> int:
    try:
        value = float(raw_id)
    except (TypeError, ValueError) as exc:
        raise CatalogError(f"PLASQLID {raw_id!r} no es numérico") from exc
    if not value.is_integer():
        raise CatalogError(f"PLASQLID {raw_id!r} no es un entero (viene con decimales)")
    return int(value)
