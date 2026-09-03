import logging

import pytest

from src.db.catalog_repository import CatalogEntry, CatalogError, build_catalog


def row(plasqlid, nombre="nombre", descripcion="desc", sentencia="select 1 from t"):
    return (plasqlid, nombre, descripcion, sentencia)


def test_basic_rows_become_catalog_entries():
    rows = [row(147.0, "A", "desc A", "select 1 from t"), row(420.0, "B", "desc B", "select 2 from t")]
    catalog = build_catalog(rows)
    assert catalog == [
        CatalogEntry(plasqlid=147, nombre="A", descripcion="desc A", sentencia="select 1 from t"),
        CatalogEntry(plasqlid=420, nombre="B", descripcion="desc B", sentencia="select 2 from t"),
    ]


def test_result_sorted_by_plasqlid_regardless_of_input_order():
    rows = [row(420.0), row(3.0), row(147.0)]
    catalog = build_catalog(rows)
    assert [e.plasqlid for e in catalog] == [3, 147, 420]


def test_exact_duplicate_rows_collapse_to_one_and_log_a_warning(caplog):
    rows = [
        row(147.0, "A", "desc A", "select 1 from t"),
        row(147.0, "A", "desc A", "select 1 from t"),
    ]
    with caplog.at_level(logging.WARNING):
        catalog = build_catalog(rows)
    assert len(catalog) == 1
    assert any("duplicada" in r.message for r in caplog.records)


def test_same_plasqlid_different_sentencia_raises():
    rows = [
        row(147.0, "A", "desc A", "select 1 from t"),
        row(147.0, "A", "desc A", "select 2 from t"),
    ]
    with pytest.raises(CatalogError, match="147 aparece más de una vez"):
        build_catalog(rows)


def test_non_integer_plasqlid_raises():
    rows = [row(147.5)]
    with pytest.raises(CatalogError, match="no es un entero"):
        build_catalog(rows)


def test_non_numeric_plasqlid_raises():
    rows = [row("abc")]
    with pytest.raises(CatalogError, match="no es numérico"):
        build_catalog(rows)


def test_empty_sentencia_raises():
    rows = [row(147.0, sentencia=None)]
    with pytest.raises(CatalogError, match="PLASQLSENT vacío"):
        build_catalog(rows)


def test_blank_sentencia_raises():
    rows = [row(147.0, sentencia="   ")]
    with pytest.raises(CatalogError, match="PLASQLSENT vacío"):
        build_catalog(rows)


def test_empty_rows_returns_empty_catalog():
    assert build_catalog([]) == []


def test_nombre_and_descripcion_are_stripped():
    rows = [row(147.0, nombre="  A  ", descripcion="  desc A  ")]
    catalog = build_catalog(rows)
    assert catalog[0].nombre == "A"
    assert catalog[0].descripcion == "desc A"
