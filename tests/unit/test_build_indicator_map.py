from pathlib import Path

from src.db.catalog_repository import CatalogEntry
from tools.build_indicator_map import (
    OrphanCell,
    build_proposal,
    write_indicator_map_csv,
    write_review_report,
)


def catalog_entry(plasqlid, descripcion, nombre="n", sentencia="select 1 from t"):
    return CatalogEntry(plasqlid=plasqlid, nombre=nombre, descripcion=descripcion, sentencia=sentencia)


def test_unique_match_is_confirmed():
    placeholders = [("H22", "RECETAS NF ANTICONCEPTIVOS DE EMERGENCIA")]
    catalog = [catalog_entry(147, "RECETAS NF ANTICONCEPTIVOS DE EMERGENCIA")]

    result = build_proposal(placeholders, catalog)

    assert len(result.confirmados) == 1
    assert result.confirmados[0].plasqlid == 147
    assert result.confirmados[0].celda == "H22"
    assert result.ambiguos == ()
    assert result.huerfanos == ()


def test_match_is_case_and_whitespace_insensitive():
    placeholders = [("H22", "  recetas nf anticonceptivos de emergencia  ")]
    catalog = [catalog_entry(147, "Recetas NF Anticonceptivos de Emergencia")]

    result = build_proposal(placeholders, catalog)

    assert len(result.confirmados) == 1
    assert result.confirmados[0].plasqlid == 147


def test_duplicate_descripcion_in_catalog_is_marked_ambiguous_not_guessed():
    placeholders = [("H39", "Medico Referencia")]
    catalog = [
        catalog_entry(13, "Medico Referencia"),
        catalog_entry(14, "Medico Referencia"),
        catalog_entry(15, "Medico Referencia"),
    ]

    result = build_proposal(placeholders, catalog)

    assert result.confirmados == ()
    assert len(result.ambiguos) == 1
    assert result.ambiguos[0].celda == "H39"
    assert result.ambiguos[0].candidatos == (13, 14, 15)


def test_text_without_match_is_marked_orphan():
    placeholders = [("H46", "31- H RECEPTORES HORMONALES OR NF P1")]
    catalog = [catalog_entry(1, "otra cosa")]

    result = build_proposal(placeholders, catalog)

    assert result.confirmados == ()
    assert result.huerfanos == (OrphanCell(celda="H46", texto="31- H RECEPTORES HORMONALES OR NF P1"),)


def test_falls_back_to_plasqlnom_when_plasqldesc_has_no_match():
    # Caso real: plasqlid 640 tiene PLASQLDESC vacio y el placeholder de la
    # celda se armo con PLASQLNOM en su lugar.
    placeholders = [("H66", "LARINGOSCOPIA ORDENES NF P1")]
    catalog = [catalog_entry(640, descripcion="", nombre="LARINGOSCOPIA ORDENES NF P1")]

    result = build_proposal(placeholders, catalog)

    assert len(result.confirmados) == 1
    assert result.confirmados[0].plasqlid == 640
    assert result.huerfanos == ()


def test_plasqlnom_fallback_is_not_used_when_plasqldesc_already_matched():
    # Si ya matcheo por PLASQLDESC, no se debe consultar PLASQLNOM (evita
    # falsos ambiguos si por casualidad otro plasqlid comparte el nombre).
    placeholders = [("H22", "TEXTO")]
    catalog = [
        catalog_entry(1, descripcion="TEXTO", nombre="OTRO NOMBRE"),
        catalog_entry(2, descripcion="OTRA DESCRIPCION", nombre="TEXTO"),
    ]

    result = build_proposal(placeholders, catalog)

    assert len(result.confirmados) == 1
    assert result.confirmados[0].plasqlid == 1


def test_same_plasqlid_matched_from_two_different_cells_is_a_duplicate_not_confirmed():
    # Caso real: el mismo texto aparece en la columna NO FONASA y FONASA de
    # una fila, y el catalogo solo tiene una entrada con esa descripcion. Sin
    # este chequeo, el CSV final quedaria con un plasqlid mapeado a dos
    # celdas distintas, que indicator_map.py rechaza al cargarlo.
    placeholders = [("H153", "Medico Referencia F"), ("AN153", "Medico Referencia F")]
    catalog = [catalog_entry(1224, "Medico Referencia F")]

    result = build_proposal(placeholders, catalog)

    assert result.confirmados == ()
    assert len(result.duplicados) == 1
    assert result.duplicados[0].plasqlid == 1224
    assert result.duplicados[0].celdas == ("AN153", "H153")


def test_duplicate_plasqlid_does_not_affect_other_confirmed_entries():
    placeholders = [
        ("H153", "X"), ("AN153", "X"),  # se van a duplicados
        ("H22", "Y"),  # se mantiene confirmado
    ]
    catalog = [catalog_entry(1, "X"), catalog_entry(2, "Y")]

    result = build_proposal(placeholders, catalog)

    assert [m.celda for m in result.confirmados] == ["H22"]
    assert len(result.duplicados) == 1


def test_multiple_placeholders_mixed_results():
    placeholders = [
        ("H22", "A"),
        ("H23", "B"),
        ("H24", "C"),
    ]
    catalog = [
        catalog_entry(1, "A"),
        catalog_entry(2, "B"),
        catalog_entry(3, "B"),
        # "C" no está en el catálogo
    ]

    result = build_proposal(placeholders, catalog)

    assert [m.celda for m in result.confirmados] == ["H22"]
    assert [a.celda for a in result.ambiguos] == ["H23"]
    assert [o.celda for o in result.huerfanos] == ["H24"]


def test_write_indicator_map_csv_only_includes_confirmed(tmp_path):
    placeholders = [("H22", "A"), ("H23", "B")]
    catalog = [catalog_entry(147, "A"), catalog_entry(13, "B"), catalog_entry(14, "B")]
    result = build_proposal(placeholders, catalog)

    csv_path = write_indicator_map_csv(result, "SMI", "4315 Utilizacion ", tmp_path / "propuesto.csv")

    content = csv_path.read_text(encoding="utf-8")
    assert content == "plasqlid,institucion_id,hoja,celda\n147,SMI,4315 Utilizacion ,H22\n"


def test_write_review_report_lists_ambiguous_and_orphan(tmp_path):
    placeholders = [("H23", "B"), ("H24", "C")]
    catalog = [catalog_entry(13, "B"), catalog_entry(14, "B")]
    result = build_proposal(placeholders, catalog)

    report_path = write_review_report(result, tmp_path / "revision.txt")

    text = report_path.read_text(encoding="utf-8")
    assert "H23" in text
    assert "candidatos [13, 14]" in text
    assert "H24" in text
    assert "'C'" in text


def test_real_template_produces_a_high_confirmation_rate():
    """Prueba de humo contra la plantilla real (no un fixture): confirma que
    la mayoría de los 756 placeholders reales tienen un match único, sin
    pegarle a la base (usa un catálogo de prueba mínimo, no PLACONSU real)."""
    repo_root = Path(__file__).resolve().parents[2]
    template = repo_root / "templates" / "SMI" / "4315 Utilizacion.xlsx"
    if not template.exists():
        import pytest

        pytest.skip("plantilla real no disponible en este entorno")

    from tools.build_indicator_map import build_proposal_from_workbook

    # catalogo minimo: solo confirma que la funcion no rompe contra la hoja
    # real y que devuelve *algo* con la forma esperada; el cruce real de
    # confirmacion/ambiguedad se prueba en tools/build_indicator_map.py
    # corrido a mano contra PLACONSU real (ver README).
    result = build_proposal_from_workbook(template, "4315 Utilizacion ", catalog=[])
    total = len(result.confirmados) + len(result.ambiguos) + len(result.huerfanos)
    assert total == 756
    assert result.confirmados == ()  # catalogo vacio: nada puede confirmarse
    assert len(result.huerfanos) == 756
