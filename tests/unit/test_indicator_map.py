import logging
from pathlib import Path

import pytest

from src.core.indicator_map import IndicatorMapEntry, IndicatorMapError, load_indicator_map

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_CONFIG_CSV = REPO_ROOT / "config" / "indicator_map.csv"


def write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "indicator_map.csv"
    p.write_text(content, encoding="utf-8")
    return p


def test_real_config_csv_loads_ok():
    entries = load_indicator_map(REAL_CONFIG_CSV)
    assert len(entries) == 8
    assert entries[0].plasqlid == 147
    assert entries[0].institucion_id == "SMI"
    assert entries[0].hoja == "DJ"
    assert entries[0].celda == "G22"


def test_valid_csv_loads_ok(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n"
        "147,SMI,DJ,G22\n"
        "420,SMI,DJ,G30\n",
    )
    entries = load_indicator_map(csv_path)
    assert entries == [
        IndicatorMapEntry(plasqlid=147, institucion_id="SMI", hoja="DJ", celda="G22"),
        IndicatorMapEntry(plasqlid=420, institucion_id="SMI", hoja="DJ", celda="G30"),
    ]


def test_duplicate_plasqlid_different_cells_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n"
        "147,SMI,DJ,G22\n"
        "147,SMI,DJ,G23\n",
    )
    with pytest.raises(IndicatorMapError, match="147"):
        load_indicator_map(csv_path)


def test_duplicate_plasqlid_same_cell_does_not_raise(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n"
        "147,SMI,DJ,G22\n"
        "147,SMI,DJ,G22\n",
    )
    entries = load_indicator_map(csv_path)
    assert len(entries) == 2


def test_duplicate_plasqlid_different_institucion_does_not_raise(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n"
        "147,SMI,DJ,G22\n"
        "147,OTRA,DJ,G22\n",
    )
    entries = load_indicator_map(csv_path)
    assert len(entries) == 2


def test_invalid_cell_format_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n147,SMI,DJ,22G\n",
    )
    with pytest.raises(IndicatorMapError, match="22G"):
        load_indicator_map(csv_path)


def test_non_integer_plasqlid_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\nabc,SMI,DJ,G22\n",
    )
    with pytest.raises(IndicatorMapError, match="abc"):
        load_indicator_map(csv_path)


def test_blank_institucion_id_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n147,,DJ,G22\n",
    )
    with pytest.raises(IndicatorMapError, match="institucion_id"):
        load_indicator_map(csv_path)


def test_blank_hoja_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,hoja,celda\n147,SMI,,G22\n",
    )
    with pytest.raises(IndicatorMapError, match="falta hoja"):
        load_indicator_map(csv_path)


def test_missing_required_column_raises(tmp_path):
    csv_path = write_csv(
        tmp_path,
        "plasqlid,institucion_id,celda\n147,SMI,G22\n",
    )
    with pytest.raises(IndicatorMapError, match="hoja"):
        load_indicator_map(csv_path)


def test_empty_csv_does_not_raise_but_warns(tmp_path, caplog):
    csv_path = write_csv(tmp_path, "plasqlid,institucion_id,hoja,celda\n")
    with caplog.at_level(logging.WARNING):
        entries = load_indicator_map(csv_path)
    assert entries == []
    assert any("no tiene filas de datos" in record.message for record in caplog.records)
