"""Variante interina de la GUI: usa SQL Server tanto para el catálogo como
para el "data warehouse" (misma base MAGIK, que hoy tiene DWFARREC/CLASCAT
cargadas con datos reales de prueba), en vez del conector Oracle real
(pendiente, ver README sección "Pendiente de Fase 2"). Es el equivalente
para la GUI de scripts/run_export_test_mssql.py (esa es la variante para el
CLI).

No es una ventana distinta ni duplica la interfaz: reutiliza
gui.app.ExportadorApp tal cual, solo reemplaza de dónde saca la conexión al
data warehouse y qué archivo de mapeo de indicadores usa por defecto (el real,
config/indicator_map.csv, todavía tiene filas de ejemplo que apuntan a tablas
que no existen; config/indicator_map.test_mssql.csv solo tiene las que sí
tienen datos reales cargados hoy).

Uso (código fuente):
    python gui/app_test_mssql.py

Empaquetado:
    pyinstaller build/exportador_test_mssql.spec

Este archivo es transitorio: cuando el conector Oracle esté implementado y
`indicator_map.csv` tenga el mapeo real completo, se deja de usar y se pasa
a `gui/app.py` / `build/exportador.spec` directamente.
"""

from __future__ import annotations

import logging
import tkinter as tk

import gui.app as app
from src.db.connection import get_connection

# Unica diferencia real con gui/app.py: dw_conn también apunta a SQL Server
# (interinamente, la misma base MAGIK ya tiene DWFARREC/CLASCAT cargadas),
# en vez del conector Oracle real (pendiente); y el mapeo de indicadores por
# defecto es el subconjunto que hoy tiene datos reales.
app.get_dw_connection = get_connection
app.DEFAULT_INDICATOR_MAP_CSV = app.BASE_DIR / "config" / "indicator_map.test_mssql.csv"


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = tk.Tk()
    app.ExportadorApp(root)
    root.title("Exportador de Indicadores (PRUEBA - datos MSSQL interinos)")
    root.mainloop()


if __name__ == "__main__":
    main()
