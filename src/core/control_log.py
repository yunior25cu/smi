"""Genera el log de control de una corrida: indicadores sin celda mapeada,
celdas mapeadas con plasqlid inexistente en el catálogo, e indicadores con
resultado NULL/vacío. Legible por un humano (regla transversal 7 del
prompt), no solo un log técnico.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from src.core.indicator_map import IndicatorMapEntry
from src.db.catalog_repository import CatalogEntry


@dataclass(frozen=True)
class ControlLog:
    institucion_id: str
    anio: int
    mes: int
    indicadores_sin_celda: tuple[CatalogEntry, ...]
    celdas_huerfanas: tuple[IndicatorMapEntry, ...]
    indicadores_nulos: tuple[IndicatorMapEntry, ...]

    def has_issues(self) -> bool:
        return bool(self.indicadores_sin_celda or self.celdas_huerfanas or self.indicadores_nulos)


def build_control_log(
    institucion_id: str,
    anio: int,
    mes: int,
    catalog: Sequence[CatalogEntry],
    mapped_entries: Sequence[IndicatorMapEntry],
    values: dict[int, float | None],
) -> ControlLog:
    mapped_ids = {m.plasqlid for m in mapped_entries}
    catalog_ids = {c.plasqlid for c in catalog}

    indicadores_sin_celda = tuple(
        sorted((c for c in catalog if c.plasqlid not in mapped_ids), key=lambda c: c.plasqlid)
    )
    celdas_huerfanas = tuple(
        sorted((m for m in mapped_entries if m.plasqlid not in catalog_ids), key=lambda m: m.plasqlid)
    )
    indicadores_nulos = tuple(
        sorted(
            (m for m in mapped_entries if m.plasqlid in catalog_ids and values.get(m.plasqlid) is None),
            key=lambda m: m.plasqlid,
        )
    )

    return ControlLog(
        institucion_id=institucion_id,
        anio=anio,
        mes=mes,
        indicadores_sin_celda=indicadores_sin_celda,
        celdas_huerfanas=celdas_huerfanas,
        indicadores_nulos=indicadores_nulos,
    )


def render_text(log: ControlLog) -> str:
    lines = [f"=== Log de control: {log.institucion_id} {log.anio:04d}-{log.mes:02d} ==="]

    lines.append("")
    lines.append(f"Indicadores del catálogo sin celda mapeada ({len(log.indicadores_sin_celda)}):")
    if log.indicadores_sin_celda:
        for c in log.indicadores_sin_celda:
            lines.append(f"  - {c.plasqlid}: {c.descripcion or c.nombre}")
    else:
        lines.append("  (ninguno)")

    lines.append("")
    lines.append(f"Celdas mapeadas cuyo plasqlid no existe en el catálogo ({len(log.celdas_huerfanas)}):")
    if log.celdas_huerfanas:
        for m in log.celdas_huerfanas:
            lines.append(f"  - plasqlid {m.plasqlid} -> {m.hoja}!{m.celda}")
    else:
        lines.append("  (ninguna)")

    lines.append("")
    lines.append(f"Indicadores con resultado NULL/vacío ({len(log.indicadores_nulos)}):")
    if log.indicadores_nulos:
        for m in log.indicadores_nulos:
            lines.append(f"  - plasqlid {m.plasqlid} (celda {m.celda})")
    else:
        lines.append("  (ninguno)")

    return "\n".join(lines) + "\n"


def write_text(log: ControlLog, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_text(log), encoding="utf-8")
    return path


def write_csv(log: ControlLog, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["seccion", "plasqlid", "detalle"])
        for c in log.indicadores_sin_celda:
            writer.writerow(["sin_celda_mapeada", c.plasqlid, c.descripcion or c.nombre])
        for m in log.celdas_huerfanas:
            writer.writerow(["celda_huerfana", m.plasqlid, f"{m.hoja}!{m.celda}"])
        for m in log.indicadores_nulos:
            writer.writerow(["resultado_nulo", m.plasqlid, m.celda])
    return path
