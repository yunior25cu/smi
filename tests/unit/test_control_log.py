from src.core.control_log import build_control_log, render_text, write_csv, write_text
from src.core.indicator_map import IndicatorMapEntry
from src.db.catalog_repository import CatalogEntry


def catalog_entry(plasqlid, nombre="n", descripcion="d", sentencia="select 1 from t"):
    return CatalogEntry(plasqlid=plasqlid, nombre=nombre, descripcion=descripcion, sentencia=sentencia)


def map_entry(plasqlid, celda, institucion_id="SMI", hoja="4315 Utilizacion "):
    return IndicatorMapEntry(plasqlid=plasqlid, institucion_id=institucion_id, hoja=hoja, celda=celda)


def build_scenario():
    catalog = [
        catalog_entry(1, descripcion="Indicador 1"),
        catalog_entry(2, descripcion="Indicador 2"),
        catalog_entry(3, descripcion="Indicador 3 sin mapear"),
    ]
    mapped_entries = [
        map_entry(1, "H22"),
        map_entry(2, "H23"),
        map_entry(99, "H24"),  # huérfano: no está en el catálogo
    ]
    values = {1: 10.0, 2: None}
    texto_residual = [("H25", "TEXTO PLACEHOLDER SIN MAPEAR")]
    return catalog, mapped_entries, values, texto_residual


def test_detects_the_four_kinds_of_discrepancy():
    catalog, mapped_entries, values, texto_residual = build_scenario()
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, values, texto_residual)

    assert [c.plasqlid for c in log.indicadores_sin_celda] == [3]
    assert [m.plasqlid for m in log.celdas_huerfanas] == [99]
    assert [m.plasqlid for m in log.indicadores_nulos] == [2]
    assert log.celdas_con_texto_residual == (("H25", "TEXTO PLACEHOLDER SIN MAPEAR"),)
    assert log.has_issues() is True


def test_no_issues_when_everything_matches():
    catalog = [catalog_entry(1)]
    mapped_entries = [map_entry(1, "H22")]
    values = {1: 10.0}
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, values)

    assert log.indicadores_sin_celda == ()
    assert log.celdas_huerfanas == ()
    assert log.indicadores_nulos == ()
    assert log.celdas_con_texto_residual == ()
    assert log.has_issues() is False


def test_texto_residual_alone_counts_as_an_issue():
    catalog = [catalog_entry(1)]
    mapped_entries = [map_entry(1, "H22")]
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, {1: 10.0}, [("H30", "texto")])
    assert log.has_issues() is True


def test_render_text_includes_the_four_sections_and_counts():
    catalog, mapped_entries, values, texto_residual = build_scenario()
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, values, texto_residual)
    text = render_text(log)

    assert "SMI 2026-08" in text
    assert "sin celda mapeada (1)" in text
    assert "Indicador 3 sin mapear" in text
    assert "no existe en el catálogo (1)" in text
    assert "plasqlid 99 -> 4315 Utilizacion !H24" in text
    assert "NULL/vacío (1)" in text
    assert "plasqlid 2 (celda H23)" in text
    assert "en vez de un número (1)" in text
    assert "H25: 'TEXTO PLACEHOLDER SIN MAPEAR'" in text


def test_render_text_says_none_when_no_issues():
    catalog = [catalog_entry(1)]
    mapped_entries = [map_entry(1, "H22")]
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, {1: 10.0})
    text = render_text(log)
    assert text.count("(ninguno)") == 2
    assert text.count("(ninguna)") == 2


def test_write_text_creates_file_with_same_content(tmp_path):
    catalog, mapped_entries, values, texto_residual = build_scenario()
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, values, texto_residual)
    path = write_text(log, tmp_path / "sub" / "control.txt")

    assert path.exists()
    assert path.read_text(encoding="utf-8") == render_text(log)


def test_write_csv_has_one_row_per_discrepancy(tmp_path):
    catalog, mapped_entries, values, texto_residual = build_scenario()
    log = build_control_log("SMI", 2026, 8, catalog, mapped_entries, values, texto_residual)
    path = write_csv(log, tmp_path / "control.csv")

    rows = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(rows) == 5  # encabezado + 4 discrepancias
