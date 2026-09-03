from pathlib import Path

import openpyxl
import pytest

from src.excel.template_writer import TemplateWriterError, write_values

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_workbook.xlsx"


def test_fixture_exists():
    assert FIXTURE.exists(), "corré scripts/build_test_fixture.py para generarlo"


def test_writes_values_at_the_right_cells(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 999.99, "D2": 111.11})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    assert dj["C2"].value == 999.99
    assert dj["D2"].value == 111.11


def test_does_not_modify_the_original_template(tmp_path):
    output = tmp_path / "out.xlsx"
    original_bytes = FIXTURE.read_bytes()

    write_values(FIXTURE, output, "DJ", {"C2": 999.99})

    assert FIXTURE.read_bytes() == original_bytes


def test_preserves_number_format_of_written_cells(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 999.99})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    assert dj["C2"].number_format == "0.00"


def test_unmapped_cells_stay_intact(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 999.99})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    # C3/D3 no estan en el dict de valores: deben quedar como en la plantilla.
    assert dj["C3"].value == 200.0
    assert dj["D3"].value == 75.5
    assert dj["F1"].value == "no tocar"


def test_merged_cells_are_preserved(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 999.99})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    assert "A2:B2" in [str(r) for r in dj.merged_cells.ranges]


def test_sheet_protection_is_preserved_without_needing_the_password(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 999.99})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    assert dj.protection.sheet is True


def test_none_value_is_written_as_empty_cell(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": None})

    wb = openpyxl.load_workbook(output)
    dj = wb["DJ"]
    assert dj["C2"].value is None


def test_missing_template_raises_clear_error(tmp_path):
    output = tmp_path / "out.xlsx"
    with pytest.raises(TemplateWriterError, match="no existe"):
        write_values(tmp_path / "no_existe.xlsx", output, "DJ", {"C2": 1})


def test_missing_sheet_raises_clear_error(tmp_path):
    output = tmp_path / "out.xlsx"
    with pytest.raises(TemplateWriterError, match="HOJA_INEXISTENTE"):
        write_values(FIXTURE, output, "HOJA_INEXISTENTE", {"C2": 1})


def test_rerunning_for_the_same_output_overwrites_it(tmp_path):
    output = tmp_path / "out.xlsx"
    write_values(FIXTURE, output, "DJ", {"C2": 1.0})
    write_values(FIXTURE, output, "DJ", {"C2": 2.0})

    wb = openpyxl.load_workbook(output)
    assert wb["DJ"]["C2"].value == 2.0
