"""Pruebas contra la base real. Se saltean automáticamente (pytest.skip) si
no hay conexión disponible en el entorno donde corre pytest (ej. CI sin
acceso a la red interna) — no hace falta ninguna variable de entorno extra
para activarlas, alcanza con que config/.env o las variables de entorno del
SO tengan una conexión válida.

Hallazgo de Fase 2: en el servidor Ryzen7PC\\SQLEXPRESS, la base MAGIK
contiene únicamente la tabla PLACONSU (el catálogo), no las tablas del data
warehouse que referencian las PLASQLSENT (dwfarrec, DWAfilia, DWTecOrd,
clascat, etc. — no existen en ninguna base de este servidor, se verificó
contra sys.databases). El servidor real donde vive ese data warehouse queda
pendiente de que lo indique el usuario (ver README, sección "Pendiente de
Fase 2"). Mientras tanto, la ejecución real de una PLASQLSENT completa contra
esas tablas se saltea con un mensaje explícito en vez de reportarse como test
roto.
"""

import pytest

from src.db.catalog_repository import fetch_catalog
from src.db.connection import get_connection
from src.db.query_builder import build_consolidated_query, fetch_indicator_values

pytestmark = pytest.mark.integration


@pytest.fixture
def conn():
    try:
        connection = get_connection()
    except Exception as exc:
        pytest.skip(f"sin conexión a la base real disponible: {exc}")
    yield connection
    connection.close()


def test_fetch_catalog_returns_a_non_empty_list(conn):
    catalog = fetch_catalog(conn)
    assert len(catalog) > 0
    assert all(entry.plasqlid > 0 for entry in catalog)


def test_fetch_indicator_values_against_a_few_real_indicators(conn):
    catalog = fetch_catalog(conn)
    by_id = {e.plasqlid: e for e in catalog}
    # 147 y 420 no usan placeholders sin resolver (ver test de @Servicios@ abajo
    # para el caso de un plasqlid que sí los usa, ej. el 3).
    sample_ids = [pid for pid in (147, 420) if pid in by_id]
    assert sample_ids, "ninguno de los plasqlid de muestra está en el catálogo real"

    sample_catalog = [by_id[pid] for pid in sample_ids]
    try:
        values = fetch_indicator_values(conn, sample_catalog, 2026, 1)
    except Exception as exc:
        if "Invalid object name" in str(exc):
            pytest.skip(
                "las tablas del data warehouse que referencia PLASQLSENT "
                f"(ej. dwfarrec) no existen en este servidor: {exc}"
            )
        raise

    assert set(values.keys()) == set(sample_ids)
    for value in values.values():
        assert value is None or isinstance(value, float)


def test_indicator_with_servicios_placeholder_builds_without_raising(conn):
    """PLASQLID 3 usa @Servicios@ en el catálogo real. Confirmado con el
    usuario que se resuelve con el mismo filtro hardcodeado en el resto del
    catálogo (perserid in (1,101)), así que build_consolidated_query ya no
    debería fallar por esto (la ejecución sí puede fallar aparte si las
    tablas del data warehouse no están disponibles en este servidor, ver
    test_fetch_indicator_values_against_a_few_real_indicators)."""
    catalog = fetch_catalog(conn)
    by_id = {e.plasqlid: e for e in catalog}
    if 3 not in by_id:
        pytest.skip("plasqlid 3 no está en el catálogo real de este entorno")

    query = build_consolidated_query([by_id[3]], 2026, 1)
    assert "perserid in (1,101)" in query.lower()
