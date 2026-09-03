"""Utilidad de un solo uso: convierte una plantilla .xls (BIFF8 legado) a .xlsx.

No es parte del pipeline de exportación mensual. Se corre manualmente una vez
por cada plantilla de institución nueva (o cuando la plantilla maestra .xls
cambie), y a partir de ahí el pipeline (Fases 1-5) trabaja siempre sobre el
.xlsx resultante con openpyxl.

Requiere Microsoft Excel instalado (usa automatización COM vía pywin32).
Ese requisito queda confinado a esta utilidad: el pipeline de exportación en
sí no depende de Excel ni de pywin32.

Uso:
    python scripts/convert_xls_to_xlsx.py "ruta\\plantilla.xls" "ruta\\salida.xlsx"
"""

import sys
from pathlib import Path

XL_OPEN_XML_WORKBOOK = 51  # formato .xlsx


def convert(xls_path: str, xlsx_path: str) -> None:
    import win32com.client

    xls_path = str(Path(xls_path).resolve())
    xlsx_path = str(Path(xlsx_path).resolve())

    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        wb = excel.Workbooks.Open(xls_path, ReadOnly=True)
        try:
            wb.SaveAs(xlsx_path, FileFormat=XL_OPEN_XML_WORKBOOK)
        finally:
            wb.Close(False)
    finally:
        excel.Quit()


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    convert(sys.argv[1], sys.argv[2])
    print(f"Convertido: {sys.argv[1]} -> {sys.argv[2]}")


if __name__ == "__main__":
    main()
