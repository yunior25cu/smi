"""Interfaz de escritorio (Fase 6): capa de presentación pura sobre
run_export.py. No agrega lógica de negocio propia -si run_export.py necesita
cambiar de firma para acomodar algo de la GUI, ese cambio va en Fase 4, no
acá.

Decisión del usuario (Fase 6): el .exe se conecta **directo** a la base de
datos, igual que `src/cli.py` hoy (mismo `connection.py`/`.env`, mismo stub
`dw_connection.py` mientras Oracle siga pendiente). No hay un servicio
intermedio.

Las funciones de validación (`can_submit`, `parse_year_month_field`, etc.)
son puras -sin ningún import de tkinter- para poder testearlas sin levantar
una ventana. La clase `ExportadorApp` es la única parte que sí depende de
tkinter, y no se instancia al importar este módulo (solo dentro de `main()`).
"""

from __future__ import annotations

import logging
import os
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Sequence

from gui.error_messages import translate
from src.cli import months_in_range
from src.core.indicator_map import load_indicator_map
from src.core.run_export import ExportResult, run_export
from src.db.connection import get_connection
from src.db.dw_connection import get_dw_connection
from src.db.query_builder import MAX_ANIO, MIN_ANIO
from src.excel.workbook_paths import InstitutionConfig, load_institutions

logger = logging.getLogger(__name__)

# Alguien que hace doble clic en el .exe no elige el directorio de trabajo,
# así que las rutas por defecto se resuelven contra la carpeta del propio
# ejecutable (empaquetado con PyInstaller) o del proyecto (corriendo con
# `python gui/app.py`), nunca contra el cwd actual.
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DEFAULT_INSTITUTIONS_YAML = BASE_DIR / "config" / "institutions.yaml"
DEFAULT_INDICATOR_MAP_CSV = BASE_DIR / "config" / "indicator_map.csv"
DEFAULT_OUTPUT_DIR = BASE_DIR / "output"

MESES = [
    (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
    (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
    (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
]  # fmt: skip


# --------------------------------------------------------------------------
# Lógica pura (testeable sin tkinter)
# --------------------------------------------------------------------------


def is_valid_year(value: str) -> bool:
    return value.strip().isdigit() and MIN_ANIO <= int(value.strip()) <= MAX_ANIO


def is_valid_month_number(value: str) -> bool:
    return value.strip().isdigit() and 1 <= int(value.strip()) <= 12


def is_valid_year_month(value: str) -> bool:
    """Valida el formato "YYYY-MM" usado en los campos de rango."""
    partes = value.strip().split("-")
    if len(partes) != 2 or not all(p.isdigit() for p in partes):
        return False
    anio, mes = int(partes[0]), int(partes[1])
    return MIN_ANIO <= anio <= MAX_ANIO and 1 <= mes <= 12


def can_submit(
    institucion: str,
    use_range: bool,
    anio: str,
    mes: str,
    desde: str,
    hasta: str,
) -> bool:
    """Determina si el botón "Generar" debe estar habilitado.

    No debe poder clickearse con la institución sin seleccionar, ni con el
    período (mes único o rango, según corresponda) incompleto o inválido.
    """
    if not institucion.strip():
        return False
    if use_range:
        return is_valid_year_month(desde) and is_valid_year_month(hasta) and desde <= hasta
    return is_valid_year(anio) and is_valid_month_number(mes)


@dataclass(frozen=True)
class RunOutcome:
    """Resultado de una corrida completa (uno o varios meses), para pasar
    del hilo de trabajo al hilo principal de la interfaz."""

    results: tuple[ExportResult, ...] = ()
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def total_discrepancias(self) -> int:
        return sum(1 for r in self.results if r.control_log.has_issues())


def run_pipeline(
    institucion_id: str,
    months: Sequence[tuple[int, int]],
    *,
    institutions_yaml: Path | None = None,
    indicator_map_csv: Path | None = None,
    output_dir: Path | None = None,
    on_status: "callable[[str], None] | None" = None,
) -> RunOutcome:
    """Corre el pipeline completo para una institución y una lista de meses.

    Función pura de orquestación (sin tkinter): abre las conexiones directas
    (decisión de la Fase 6), corre run_export mes a mes, y devuelve un
    RunOutcome. `on_status` es un callback opcional para reportar progreso
    en lenguaje llano ("Consultando base de datos...", etc.).

    Los tres parámetros de ruta, si no se pasan, se resuelven contra las
    constantes del módulo **en el momento de llamar**, no al definir la
    función: así, variantes como gui/app_test_mssql.py pueden sobreescribir
    `app.DEFAULT_INDICATOR_MAP_CSV`/`app.get_dw_connection` antes de invocar
    esto y que el cambio realmente se aplique (con un default de parámetro
    normal, ligado en tiempo de definición, no se hubiese notado el cambio).
    """
    if institutions_yaml is None:
        institutions_yaml = DEFAULT_INSTITUTIONS_YAML
    if indicator_map_csv is None:
        indicator_map_csv = DEFAULT_INDICATOR_MAP_CSV
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR

    def status(msg: str) -> None:
        logger.info(msg)
        if on_status is not None:
            on_status(msg)

    try:
        status("Cargando configuración...")
        institutions = load_institutions(institutions_yaml)
        indicator_map = load_indicator_map(indicator_map_csv)

        status("Conectando a la base de datos...")
        catalog_conn = get_connection()
        dw_conn = get_dw_connection()
    except Exception as exc:  # noqa: BLE001 - se traduce en la capa de presentación
        return RunOutcome(error=exc)

    try:
        results = []
        for anio, mes in months:
            status(f"Consultando indicadores de {institucion_id} {anio:04d}-{mes:02d}...")
            result = run_export(
                institucion_id,
                anio,
                mes,
                institutions=institutions,
                indicator_map=indicator_map,
                catalog_conn=catalog_conn,
                dw_conn=dw_conn,
                output_dir=output_dir,
            )
            status(f"Escribiendo Excel de {institucion_id} {anio:04d}-{mes:02d}...")
            results.append(result)
        status("Listo.")
        return RunOutcome(results=tuple(results))
    except Exception as exc:  # noqa: BLE001 - idem
        return RunOutcome(error=exc)
    finally:
        catalog_conn.close()
        dw_conn.close()


# --------------------------------------------------------------------------
# Ventana (tkinter)
# --------------------------------------------------------------------------


class ExportadorApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Exportador de Indicadores")
        self.root.resizable(False, False)

        self._queue: "queue.Queue[object]" = queue.Queue()
        self._institutions: list[InstitutionConfig] = []

        self._build_widgets()
        self._load_institutions()
        self._update_generar_state()

    # -- construcción de la ventana -----------------------------------

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}
        frame = ttk.Frame(self.root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Institución:").grid(row=0, column=0, sticky="w", **pad)
        self.institucion_var = tk.StringVar()
        self.institucion_combo = ttk.Combobox(frame, textvariable=self.institucion_var, state="readonly", width=30)
        self.institucion_combo.grid(row=0, column=1, columnspan=3, sticky="we", **pad)
        self.institucion_var.trace_add("write", lambda *_a: self._update_generar_state())

        self.use_range_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="Rango de meses", variable=self.use_range_var, command=self._on_toggle_range
        ).grid(row=1, column=0, columnspan=2, sticky="w", **pad)

        # Mes unico
        ttk.Label(frame, text="Año:").grid(row=2, column=0, sticky="w", **pad)
        self.anio_var = tk.StringVar()
        self.anio_entry = ttk.Entry(frame, textvariable=self.anio_var, width=8)
        self.anio_entry.grid(row=2, column=1, sticky="w", **pad)
        self.anio_var.trace_add("write", lambda *_a: self._update_generar_state())

        ttk.Label(frame, text="Mes:").grid(row=2, column=2, sticky="w", **pad)
        self.mes_var = tk.StringVar()
        self.mes_combo = ttk.Combobox(
            frame, textvariable=self.mes_var, state="readonly", width=12,
            values=[f"{n:02d} - {nombre}" for n, nombre in MESES],
        )
        self.mes_combo.grid(row=2, column=3, sticky="w", **pad)
        self.mes_var.trace_add("write", lambda *_a: self._update_generar_state())

        # Rango
        ttk.Label(frame, text="Desde (AAAA-MM):").grid(row=3, column=0, sticky="w", **pad)
        self.desde_var = tk.StringVar()
        self.desde_entry = ttk.Entry(frame, textvariable=self.desde_var, width=10)
        self.desde_entry.grid(row=3, column=1, sticky="w", **pad)
        self.desde_var.trace_add("write", lambda *_a: self._update_generar_state())

        ttk.Label(frame, text="Hasta (AAAA-MM):").grid(row=3, column=2, sticky="w", **pad)
        self.hasta_var = tk.StringVar()
        self.hasta_entry = ttk.Entry(frame, textvariable=self.hasta_var, width=10)
        self.hasta_entry.grid(row=3, column=3, sticky="w", **pad)
        self.hasta_var.trace_add("write", lambda *_a: self._update_generar_state())

        self.generar_btn = ttk.Button(frame, text="Generar", command=self._on_generar)
        self.generar_btn.grid(row=4, column=0, columnspan=4, sticky="we", **pad)

        self.progress = ttk.Progressbar(frame, mode="indeterminate")
        self.progress.grid(row=5, column=0, columnspan=4, sticky="we", **pad)
        self.progress.grid_remove()

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var, foreground="gray20").grid(
            row=6, column=0, columnspan=4, sticky="w", **pad
        )

        self._on_toggle_range()

    def _on_toggle_range(self) -> None:
        use_range = self.use_range_var.get()
        state_single = "disabled" if use_range else "normal"
        state_range = "normal" if use_range else "disabled"
        self.anio_entry.configure(state=state_single)
        self.mes_combo.configure(state=("disabled" if use_range else "readonly"))
        self.desde_entry.configure(state=state_range)
        self.hasta_entry.configure(state=state_range)
        self._update_generar_state()

    def _load_institutions(self) -> None:
        try:
            self._institutions = load_institutions(DEFAULT_INSTITUTIONS_YAML)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Exportador de Indicadores", translate(exc))
            self._institutions = []
        self.institucion_combo["values"] = [c.id for c in self._institutions]
        if self._institutions:
            self.institucion_combo.current(0)

    # -- validación / estado --------------------------------------------

    def _mes_numero(self) -> str:
        valor = self.mes_var.get()
        return valor.split(" - ")[0] if valor else ""

    def _update_generar_state(self) -> None:
        habilitado = can_submit(
            institucion=self.institucion_var.get(),
            use_range=self.use_range_var.get(),
            anio=self.anio_var.get(),
            mes=self._mes_numero(),
            desde=self.desde_var.get(),
            hasta=self.hasta_var.get(),
        )
        self.generar_btn.configure(state=("normal" if habilitado else "disabled"))

    # -- generar ----------------------------------------------------------

    def _on_generar(self) -> None:
        institucion_id = self.institucion_var.get()
        if self.use_range_var.get():
            months = months_in_range(self.desde_var.get().strip(), self.hasta_var.get().strip())
        else:
            months = [(int(self.anio_var.get().strip()), int(self._mes_numero()))]

        self.generar_btn.configure(state="disabled")
        self.progress.grid()
        self.progress.start(10)
        self.status_var.set("Iniciando...")

        thread = threading.Thread(
            target=lambda: self._queue.put(
                run_pipeline(institucion_id, months, on_status=lambda msg: self._queue.put(("status", msg)))
            ),
            daemon=True,
        )
        thread.start()
        self.root.after(100, self._poll_queue)

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "status":
                    self.status_var.set(item[1])
                elif isinstance(item, RunOutcome):
                    self._on_run_finished(item)
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _on_run_finished(self, outcome: RunOutcome) -> None:
        self.progress.stop()
        self.progress.grid_remove()
        self.generar_btn.configure(state="normal")

        if not outcome.ok:
            self.status_var.set("Error.")
            messagebox.showerror("Exportador de Indicadores", translate(outcome.error))
            return

        self.status_var.set("Listo.")
        rutas = "\n".join(str(r.output_path) for r in outcome.results)
        mensaje = f"Exportación generada:\n{rutas}"
        abrir_carpeta = messagebox.askyesno(
            "Exportador de Indicadores", f"{mensaje}\n\n¿Abrir la carpeta de salida?"
        )
        if abrir_carpeta and outcome.results:
            os.startfile(outcome.results[0].output_path.parent)  # noqa: S606 - abrir carpeta en Windows

        if outcome.total_discrepancias:
            revisar = messagebox.askyesno(
                "Exportador de Indicadores",
                f"Se generó igual, pero hay {outcome.total_discrepancias} archivo(s) con "
                f"indicadores para revisar en el log de control.\n\n¿Abrir el primer log?",
            )
            if revisar:
                os.startfile(outcome.results[0].control_log_path)  # noqa: S606


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = tk.Tk()
    ExportadorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
