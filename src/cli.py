"""CLI de exportación de indicadores.

Uso:
    python -m src.cli --institucion SMI --anio 2026 --mes 8
    python -m src.cli --institucion SMI --desde 2026-01 --hasta 2026-08

Código de salida: 0 si la corrida terminó sin discrepancias, 1 si terminó
bien pero el log de control encontró alguna (ver control_log.py), 2 si no
pudo ni empezar (configuración inválida, no se pudo conectar, etc.).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from src.core.control_log import render_text
from src.core.indicator_map import IndicatorMapError, load_indicator_map
from src.core.run_export import run_export
from src.db.connection import ConnectionConfigError, get_connection
from src.db.dw_connection import get_dw_connection
from src.db.query_builder import MAX_ANIO, MIN_ANIO, QueryBuilderError
from src.excel.template_writer import TemplateWriterError
from src.excel.workbook_paths import InstitutionConfigError, load_institutions

DEFAULT_INSTITUTIONS_YAML = Path("config/institutions.yaml")
DEFAULT_INDICATOR_MAP_CSV = Path("config/indicator_map.csv")

logger = logging.getLogger(__name__)

# Errores esperables de configuración/entorno: se reportan con un mensaje de
# una línea, sin traceback (rutas de error que sí hay que manejar con
# claridad, no bugs del programa).
_KNOWN_ERRORS = (
    ConnectionConfigError,
    IndicatorMapError,
    InstitutionConfigError,
    QueryBuilderError,
    TemplateWriterError,
    NotImplementedError,  # incluye DwConnectionNotConfiguredError
    ValueError,  # incluye errores de parseo de --desde/--hasta
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Exporta indicadores SQL a la plantilla Excel de una institución."
    )
    parser.add_argument("--institucion", required=True)
    parser.add_argument("--anio", type=int)
    parser.add_argument("--mes", type=int)
    parser.add_argument("--desde", help="Primer mes del rango, formato YYYY-MM")
    parser.add_argument("--hasta", help="Último mes del rango, formato YYYY-MM")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Nivel de detalle del log (default: INFO)",
    )
    args = parser.parse_args(argv)

    if args.desde or args.hasta:
        if not (args.desde and args.hasta):
            parser.error("--desde y --hasta van siempre juntos")
        if args.anio or args.mes:
            parser.error("no combines --anio/--mes con --desde/--hasta")
    else:
        if not (args.anio and args.mes):
            parser.error("indicá --anio y --mes, o --desde y --hasta")
        if not (MIN_ANIO <= args.anio <= MAX_ANIO):
            parser.error(f"--anio {args.anio} fuera de rango ({MIN_ANIO}-{MAX_ANIO})")
        if not (1 <= args.mes <= 12):
            parser.error(f"--mes {args.mes} fuera de rango (1-12)")
    return args


def months_in_range(desde: str, hasta: str) -> list[tuple[int, int]]:
    """Expande "YYYY-MM".."YYYY-MM" (inclusive) a una lista de (año, mes)."""
    anio_desde, mes_desde = _parse_year_month(desde, "--desde")
    anio_hasta, mes_hasta = _parse_year_month(hasta, "--hasta")
    if (anio_hasta, mes_hasta) < (anio_desde, mes_desde):
        raise ValueError(f"--hasta ({hasta}) es anterior a --desde ({desde})")

    months = []
    anio, mes = anio_desde, mes_desde
    while (anio, mes) <= (anio_hasta, mes_hasta):
        months.append((anio, mes))
        mes += 1
        if mes == 13:
            mes = 1
            anio += 1
    return months


def _parse_year_month(value: str, flag: str) -> tuple[int, int]:
    partes = value.split("-")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        raise ValueError(f"{flag} {value!r} debe tener formato YYYY-MM")
    anio, mes = int(partes[0]), int(partes[1])
    if not (MIN_ANIO <= anio <= MAX_ANIO):
        raise ValueError(f"{flag} {value!r}: año fuera de rango ({MIN_ANIO}-{MAX_ANIO})")
    if not (1 <= mes <= 12):
        raise ValueError(f"{flag} {value!r}: mes fuera de rango (1-12)")
    return anio, mes


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


def _run(args: argparse.Namespace) -> int:
    months = months_in_range(args.desde, args.hasta) if args.desde else [(args.anio, args.mes)]

    institutions = load_institutions(DEFAULT_INSTITUTIONS_YAML)
    indicator_map = load_indicator_map(DEFAULT_INDICATOR_MAP_CSV)

    catalog_conn = None
    dw_conn = None
    try:
        catalog_conn = get_connection()
        dw_conn = get_dw_connection()

        exit_code = 0
        for anio, mes in months:
            logger.info("exportando institución=%s anio=%s mes=%s", args.institucion, anio, mes)
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
                logger.warning("%s: el log de control encontró discrepancias", result.output_path)
                exit_code = 1
            else:
                logger.info("%s: sin discrepancias", result.output_path)
        return exit_code
    finally:
        if catalog_conn is not None:
            catalog_conn.close()
        if dw_conn is not None:
            dw_conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
