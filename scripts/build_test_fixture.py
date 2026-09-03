"""Genera tests/fixtures/sample_workbook.xlsx: un workbook mínimo sintético
para los tests de template_writer.py, con la misma forma que la plantilla
real (hoja DJ, protegida, con celdas combinadas y number_format propio) pero
sin ningún dato de producción.

Se corre una sola vez (o cuando haga falta ajustar el fixture); el archivo
resultante se versiona en git (es la única excepción a "no versionar .xlsx"
del .gitignore).

Uso:
    python scripts/build_test_fixture.py
"""

from pathlib import Path

import openpyxl

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_workbook.xlsx"


def build() -> None:
    wb = openpyxl.Workbook()
    dj = wb.active
    dj.title = "DJ"

    # Encabezados, como en la plantilla real (fila 11 en la real; acá basta
    # con algo simple).
    dj["A1"] = "CONCEPTO"
    dj["C1"] = "VALOR MAXIMO AUTORIZADO"
    dj["D1"] = "PRECIO 1"

    # Fila de concepto con celdas combinadas horizontal (A2:B2, como
    # A13:E13 en la plantilla real) y number_format propio en las celdas de
    # valor.
    dj["A2"] = "CONCEPTO DE EJEMPLO 1"
    dj.merge_cells("A2:B2")
    dj["C2"] = 100.5
    dj["C2"].number_format = "0.00"
    dj["D2"] = 50.25
    dj["D2"].number_format = "0.00"

    # Segunda fila de concepto, sin mapear en los tests: sirve para
    # comprobar que una celda no mapeada queda intacta.
    dj["A3"] = "CONCEPTO DE EJEMPLO 2 (no mapeado en los tests)"
    dj["C3"] = 200.0
    dj["C3"].number_format = "0.00"
    dj["D3"] = 75.5
    dj["D3"].number_format = "0.00"

    # Celda de texto fuera del área de valores, para comprobar que
    # template_writer no toca nada que no esté en el dict de valores.
    dj["F1"] = "no tocar"

    # Protección de hoja con contraseña real, como la plantilla real: hay
    # que verificar (Fase 0/3) que openpyxl puede escribir igual sin ella.
    dj.protection.sheet = True
    dj.protection.set_password("fixture-password")

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(FIXTURE_PATH)
    print(f"Generado: {FIXTURE_PATH}")


if __name__ == "__main__":
    build()
