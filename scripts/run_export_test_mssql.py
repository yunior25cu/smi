"""Corre una exportación real usando SOLO SQL Server, para probar el pipeline
completo mientras el conector Oracle definitivo (src/db/dw_connection.py)
sigue pendiente (pospuesto a propósito, ver README).

Diferencia con `python -m src.cli`: ese comando es la interfaz FINAL de
producción y abre dos conexiones (catálogo en SQL Server, ejecución en
Oracle) — hoy falla a propósito en la segunda porque Oracle no está
conectado todavía. Este script, en cambio, abre las dos conexiones contra la
MISMA base SQL Server (`MAGIK`), que hoy también tiene las tablas de datos
reales (`DWFARREC`, `CLASCAT`) cargadas para poder probar de punta a punta.

También usa, por defecto, `config/indicator_map.test_mssql.csv` en vez de
`config/indicator_map.csv`: ese archivo solo tiene las filas que hoy tienen
tablas reales cargadas (147 y 94, ambos basados en `dwfarrec`); el
`indicator_map.csv` "real" todavía tiene filas de ejemplo que apuntan a
tablas que no existen (`DWAfilia`, `DWTecOrd`, etc.), y correr TODO ese
archivo junto rompería la consulta consolidada completa (un solo indicador
con tabla faltante frena a todos, por diseño: es una sola query UNION ALL).

Uso (igual que `src.cli`, mismos parámetros):
    python scripts/run_export_test_mssql.py --institucion SMI --anio 2026 --mes 5
    python scripts/run_export_test_mssql.py --institucion SMI --desde 2026-01 --hasta 2026-05

Este script es transitorio: cuando el conector Oracle esté implementado y
`indicator_map.csv` tenga el mapeo real completo, dejar de usarlo y usar
`python -m src.cli` directamente.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Sequence

# Permite correr este script directamente (python scripts/run_export_test_mssql.py)
# desde cualquier directorio, sin instalar el proyecto como paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cli import _KNOWN_ERRORS, months_in_range, parse_args
from src.core.control_log import render_text
from src.core.indicator_map import load_indicator_map
from src.core.run_export import run_export
from src.db.connection import get_connection
from src.excel.workbook_paths import load_institutions

DEFAULT_INSTITUTIONS_YAML = Path("config/institutions.yaml")
DEFAULT_INDICATOR_MAP_CSV = Path("config/indicator_map.test_mssql.csv")

logger = logging.getLogger(__name__)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        return _run(args)
    except _KNOWN_ERRORS as exc:
        logger.error("%s", exc)
        print(f"Error: {exc}", file=sys.stderr)
        return 2


def _run(args) -> int:
    months = months_in_range(args.desde, args.hasta) if args.desde else [(args.anio, args.mes)]

    institutions = load_institutions(DEFAULT_INSTITUTIONS_YAML)
    indicator_map = load_indicator_map(DEFAULT_INDICATOR_MAP_CSV)

    catalog_conn = None
    dw_conn = None
    try:
        # Ambas conexiones apuntan a la misma base SQL Server: es la
        # diferencia principal con src.cli.main(), que usa el conector
        # Oracle (todavía pendiente) para dw_conn.
        catalog_conn = get_connection()
        dw_conn = get_connection()

        exit_code = 0
        for anio, mes in months:
            logger.info("exportando (prueba MSSQL) institución=%s anio=%s mes=%s", args.institucion, anio, mes)
            result = run_export(
                args.institucion,
                anio,
                mes,
                institutions=institutions,
                indicator_map=indicator_map,
                catalog_conn=catalog_conn,
                dw_conn=dw_conn,
                output_dir=args.output_dir,
            )
            print(f"{result.output_path}")
            print(render_text(result.control_log))
            if result.control_log.has_issues():
                exit_code = 1
        return exit_code
    finally:
        if catalog_conn is not None:
            catalog_conn.close()
        if dw_conn is not None:
            dw_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
