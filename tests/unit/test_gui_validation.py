"""Prueba la lógica pura de validación de gui/app.py, sin levantar ninguna
ventana (importar gui.app no crea un Tk()). Verifica en particular que el
botón "Generar" quede deshabilitado con campos incompletos, como pide la
Fase 6.
"""

from gui.app import can_submit, is_valid_month_number, is_valid_year, is_valid_year_month


def test_can_submit_false_without_institucion():
    assert can_submit("", False, "2026", "8", "", "") is False


def test_can_submit_true_for_valid_single_month():
    assert can_submit("SMI", False, "2026", "8", "", "") is True


def test_can_submit_false_with_missing_anio():
    assert can_submit("SMI", False, "", "8", "", "") is False


def test_can_submit_false_with_missing_mes():
    assert can_submit("SMI", False, "2026", "", "", "") is False


def test_can_submit_false_with_out_of_range_anio():
    assert can_submit("SMI", False, "1999", "8", "", "") is False


def test_can_submit_false_with_out_of_range_mes():
    assert can_submit("SMI", False, "2026", "13", "", "") is False


def test_can_submit_true_for_valid_range():
    assert can_submit("SMI", True, "", "", "2026-01", "2026-08") is True


def test_can_submit_false_with_incomplete_range():
    assert can_submit("SMI", True, "", "", "2026-01", "") is False


def test_can_submit_false_when_range_is_reversed():
    assert can_submit("SMI", True, "", "", "2026-08", "2026-01") is False


def test_can_submit_false_with_malformed_range_value():
    assert can_submit("SMI", True, "", "", "2026/01", "2026-08") is False


def test_is_valid_year_accepts_boundaries():
    assert is_valid_year("2000") is True
    assert is_valid_year("2100") is True
    assert is_valid_year("1999") is False
    assert is_valid_year("2101") is False
    assert is_valid_year("abc") is False


def test_is_valid_month_number_accepts_1_to_12():
    assert is_valid_month_number("1") is True
    assert is_valid_month_number("12") is True
    assert is_valid_month_number("0") is False
    assert is_valid_month_number("13") is False


def test_is_valid_year_month_accepts_correct_format():
    assert is_valid_year_month("2026-08") is True
    assert is_valid_year_month("2026-13") is False
    assert is_valid_year_month("2026/08") is False
    assert is_valid_year_month("") is False
