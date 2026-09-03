"""Traduce excepciones técnicas del pipeline a mensajes de usuario en
lenguaje llano, para mostrarlos en la GUI (Fase 6).

Regla de la Fase 6: la ventana nunca muestra un stack trace de Python. El
detalle técnico completo (`str(exc)`, tipo de excepción) va al log; acá solo
se decide qué frase en español llano corresponde a cada tipo de error.

Lógica pura, sin ningún import de tkinter: se puede testear sin ventana.
"""

from __future__ import annotations

from src.core.indicator_map import IndicatorMapError
from src.db.connection import ConnectionConfigError
from src.db.dw_connection import DwConnectionNotConfiguredError
from src.db.query_builder import QueryBuilderError
from src.excel.template_writer import TemplateWriterError
from src.excel.workbook_paths import InstitutionConfigError

GENERIC_MESSAGE = "Ocurrió un error inesperado. Avisá a sistemas con el detalle del log."

# Orden: del más específico al más general. DwConnectionNotConfiguredError no
# hereda de ConnectionConfigError (son conexiones distintas: catálogo vs data
# warehouse), así que el orden entre ambas no afecta el resultado, pero se
# deja igual la más específica primero por claridad.
_TRANSLATIONS: tuple[tuple[type[Exception], str], ...] = (
    (
        DwConnectionNotConfiguredError,
        "La conexión a la base de datos de indicadores todavía no está "
        "configurada. Avisá a sistemas.",
    ),
    (
        ConnectionConfigError,
        "No se pudo conectar a la base de datos. Avisá a sistemas.",
    ),
    (
        InstitutionConfigError,
        "La institución seleccionada no está bien configurada. Avisá a sistemas.",
    ),
    (
        IndicatorMapError,
        "El archivo de configuración de indicadores tiene un error. Avisá a sistemas.",
    ),
    (
        QueryBuilderError,
        "Uno de los indicadores tiene un problema de configuración en la base "
        "de datos. Avisá a sistemas.",
    ),
    (
        TemplateWriterError,
        "No se pudo escribir la planilla: falta el archivo de plantilla o la "
        "hoja indicada. Avisá a sistemas.",
    ),
    (
        PermissionError,
        "No se pudo guardar el archivo. Puede estar abierto en otro programa, "
        "o no tenés permiso para escribir en esa carpeta.",
    ),
    (
        FileNotFoundError,
        "No se encontró un archivo necesario (plantilla o configuración). Avisá a sistemas.",
    ),
)


def translate(exc: Exception) -> str:
    """Devuelve el mensaje en español llano correspondiente a `exc`.

    Si el tipo de excepción no está mapeado, devuelve un mensaje genérico
    (nunca el texto técnico crudo de la excepción).
    """
    for exc_type, message in _TRANSLATIONS:
        if isinstance(exc, exc_type):
            return message
    return GENERIC_MESSAGE
