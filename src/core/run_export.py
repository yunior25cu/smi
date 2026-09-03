"""Orquestador: corre el pipeline completo de exportación para una institución y mes.

Recibe dos conexiones separadas -no una sola- porque en el entorno real
(hallazgo de la Fase 2) el catálogo (`MAGIK.PLACONSU`) vive en un servidor
SQL Server distinto del data warehouse (Oracle) donde se ejecutan las
PLASQLSENT. Ambas son conexiones DB-API 2.0 genéricas: quién las abre
(`src/db/connection.py`, `src/db/dw_connection.py`, o un mock en los tests)
es responsabilidad de quien llama a `run_export`, no de este módulo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from src.core.control_log import ControlLog, build_control_log, write_text
from src.core.indicator_map import IndicatorMapEntry
from src.db.catalog_repository import fetch_catalog
from src.db.query_builder import fetch_indicator_values
from src.excel.template_writer import write_values
from src.excel.workbook_paths import InstitutionConfig, get_institution, resolve_output_path


@dataclass(frozen=True)
class ExportResult:
    output_path: Path
    control_log_path: Path
    control_log: ControlLog


def run_export(
    institucion_id: str,
    anio: int,
    mes: int,
    *,
    institutions: Sequence[InstitutionConfig],
    indicator_map: Sequence[IndicatorMapEntry],
    catalog_conn,
    dw_conn,
    output_dir: str | Path = "output",
) -> ExportResult:
    """Carga el mapa de esta institución, trae el catálogo, ejecuta la query
    consolidada solo para los indicadores mapeados, escribe la plantilla y
    genera el log de control. Devuelve las rutas de ambos archivos."""
    institution = get_institution(list(institutions), institucion_id)
    mapped_entries = [m for m in indicator_map if m.institucion_id == institucion_id]

    catalog = fetch_catalog(catalog_conn)
    catalog_by_id = {c.plasqlid: c for c in catalog}

    # Deduplicado por plasqlid: dos filas del mapa pueden apuntar al mismo
    # plasqlid+celda (Fase 1 lo tolera), pero query_builder rechaza IDs
    # repetidos dentro del catálogo que se le pasa.
    ids_a_consultar = sorted({m.plasqlid for m in mapped_entries if m.plasqlid in catalog_by_id})
    indicadores_a_consultar = [catalog_by_id[pid] for pid in ids_a_consultar]
    values = fetch_indicator_values(dw_conn, indicadores_a_consultar, anio, mes) if indicadores_a_consultar else {}

    cell_values = {
        m.celda: values[m.plasqlid] for m in mapped_entries if m.plasqlid in catalog_by_id
    }

    output_path = resolve_output_path(institucion_id, anio, mes, output_dir)
    write_values(institution.plantilla, output_path, institution.hoja, cell_values)

    control_log = build_control_log(institucion_id, anio, mes, catalog, mapped_entries, values)
    control_log_path = output_path.with_name(f"{output_path.stem}_control.txt")
    write_text(control_log, control_log_path)

    return ExportResult(output_path=output_path, control_log_path=control_log_path, control_log=control_log)
