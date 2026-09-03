"""Arma y ejecuta la consulta consolidada (UNION ALL) del catálogo de indicadores.

Cada PLASQLSENT es (según la decisión 6 del prompt) un SELECT escalar. En vez
de reescribir su lista de columnas, cada sentencia se envuelve tal cual como
subquery escalar: ``(select ... ) AS valor``. Eso evita tener que parsear ni
reconstruir el SQL interno, y deja que el propio motor falle en tiempo de
ejecución si una subquery devuelve más de una fila (lo cual ya es un error
explícito de SQL Server, no un resultado adivinado).

Lo que sí valida este módulo, antes de ejecutar nada, es que cada PLASQLSENT
tenga *una sola columna* en su lista de SELECT (no se puede envolver como
subquery escalar una consulta que trae varias columnas). La validación es un
escaneo del texto que respeta paréntesis y strings entre comillas simples
-no un parser SQL completo-, suficiente para distinguir "select a, b from t"
(dos columnas, inválido) de "select isnull(a,b) from t" o
"select (select count(*) from t2) from t1" (una columna, válido). No
contempla comentarios SQL (--, /* */) dentro de PLASQLSENT.

Placeholders soportados (descubiertos corriendo esto contra el catálogo real
en Fase 2, no solo los dos documentados en el prompt):

- ``@AAAA@`` / ``@MM@``: año y mes, documentados en el prompt.
- ``@FHINICIO@`` / ``@FHFIN@``: aparecen en 112 PLASQLSENT reales (ej.
  ``tdordagfch >= @FHINICIO@``). Se sustituyen por el primer y el último día
  del mes en formato ISO entre comillas (ej. ``'2026-01-01'``), calculado con
  ``calendar.monthrange`` — no dependen de nada más que año/mes, así que se
  pueden resolver automáticamente sin ambigüedad.
- ``@Servicios@`` / ``@Servidios@`` (la segunda es un typo real en el
  catálogo, no un placeholder distinto a propósito): aparecen en 20
  PLASQLSENT reales como ``PerSerId in (@Servicios@)``. Confirmado con el
  usuario: se sustituyen por ``1,101``, el mismo filtro que aparece
  hardcodeado como ``perserid in (1,101)`` en el resto del catálogo (ver
  ``DEFAULT_SERVICIOS``).

Cualquier otro placeholder ``@algo@`` que aparezca en una PLASQLSENT y no
esté en esta lista hace fallar la construcción de la query con un error
explícito (ver ``_check_no_leftover_placeholders``), en vez de mandarle SQL
inválido al motor o de adivinarle un valor.
"""

from __future__ import annotations

import calendar
import re
from typing import Sequence

from src.db.catalog_repository import CatalogEntry

MIN_ANIO = 2000
MAX_ANIO = 2100

# Confirmado con el usuario: mismo filtro PerSerId hardcodeado en el resto
# del catálogo (ej. "perserid in (1,101)").
DEFAULT_SERVICIOS = "1,101"

_LEFTOVER_PLACEHOLDER_RE = re.compile(r"@[A-Za-z0-9_]+@")


class QueryBuilderError(ValueError):
    """El catálogo o alguna PLASQLSENT no se puede convertir en query consolidada."""


def build_consolidated_query(catalog: Sequence[CatalogEntry], anio: int, mes: int) -> str:
    """Arma un único SELECT (plasqlid, valor) a partir del catálogo completo."""
    _validate_anio_mes(anio, mes)
    _validate_no_duplicate_ids(catalog)

    if not catalog:
        raise QueryBuilderError("el catálogo está vacío, no hay nada que consultar")

    branches = []
    for entry in catalog:
        sentencia = _substitute_placeholders(entry.sentencia, anio, mes)
        _check_no_leftover_placeholders(sentencia, entry.plasqlid)
        scalar_select = _validate_scalar_select(sentencia, entry.plasqlid)
        branches.append(f"SELECT {entry.plasqlid} AS plasqlid, ({scalar_select}) AS valor")

    unioned = "\nUNION ALL\n".join(branches)
    return f"SELECT plasqlid, valor\nFROM (\n{unioned}\n) AS indicadores;"


def fetch_indicator_values(
    conn, catalog: Sequence[CatalogEntry], anio: int, mes: int
) -> dict[int, float | None]:
    """Ejecuta la query consolidada y devuelve {plasqlid: valor}.

    Un valor None significa que la subquery de ese indicador no devolvió
    filas o devolvió NULL (ej. un SUM sin filas que sumar): la Fase 4 lo
    reporta en el log de control, esta función no lo filtra ni lo esconde.
    """
    query = build_consolidated_query(catalog, anio, mes)
    cursor = conn.cursor()
    cursor.execute(query)
    return {int(row[0]): (float(row[1]) if row[1] is not None else None) for row in cursor.fetchall()}


def _validate_anio_mes(anio: int, mes: int) -> None:
    if not isinstance(anio, int) or isinstance(anio, bool) or not (MIN_ANIO <= anio <= MAX_ANIO):
        raise QueryBuilderError(f"anio {anio!r} inválido (se esperaba un entero entre {MIN_ANIO} y {MAX_ANIO})")
    if not isinstance(mes, int) or isinstance(mes, bool) or not (1 <= mes <= 12):
        raise QueryBuilderError(f"mes {mes!r} inválido (se esperaba un entero entre 1 y 12)")


def _validate_no_duplicate_ids(catalog: Sequence[CatalogEntry]) -> None:
    seen: set[int] = set()
    for entry in catalog:
        if entry.plasqlid in seen:
            raise QueryBuilderError(
                f"plasqlid {entry.plasqlid} aparece más de una vez en el catálogo "
                f"pasado a build_consolidated_query (debería haber sido "
                f"deduplicado por catalog_repository)"
            )
        seen.add(entry.plasqlid)


def _substitute_placeholders(sentencia: str, anio: int, mes: int) -> str:
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    fhinicio = f"'{anio:04d}-{mes:02d}-01'"
    fhfin = f"'{anio:04d}-{mes:02d}-{ultimo_dia:02d}'"
    return (
        sentencia.replace("@AAAA@", str(anio))
        .replace("@MM@", str(mes))
        .replace("@FHINICIO@", fhinicio)
        .replace("@FHFIN@", fhfin)
        .replace("@Servicios@", DEFAULT_SERVICIOS)
        .replace("@Servidios@", DEFAULT_SERVICIOS)
    )


def _check_no_leftover_placeholders(sentencia: str, plasqlid: int) -> None:
    leftover = sorted(set(_LEFTOVER_PLACEHOLDER_RE.findall(sentencia)))
    if leftover:
        raise QueryBuilderError(
            f"plasqlid {plasqlid}: PLASQLSENT usa placeholder(s) no soportados "
            f"{leftover} (los únicos que se sustituyen son @AAAA@, @MM@, "
            f"@FHINICIO@ y @FHFIN@); sentencia resultante tras sustituir lo "
            f"conocido: {sentencia!r}"
        )


def _validate_scalar_select(sentencia: str, plasqlid: int) -> str:
    cleaned = sentencia.strip().rstrip(";").strip()
    if not cleaned:
        raise QueryBuilderError(f"plasqlid {plasqlid}: PLASQLSENT está vacío")
    if not cleaned.lower().startswith("select"):
        raise QueryBuilderError(
            f"plasqlid {plasqlid}: PLASQLSENT no es un SELECT: {sentencia!r}"
        )
    if _has_top_level_semicolon(cleaned):
        raise QueryBuilderError(
            f"plasqlid {plasqlid}: PLASQLSENT parece tener más de una sentencia "
            f"(punto y coma en el medio): {sentencia!r}"
        )

    column_count = _count_select_columns(cleaned)
    if column_count != 1:
        raise QueryBuilderError(
            f"plasqlid {plasqlid}: PLASQLSENT no es un SELECT escalar simple "
            f"(se detectaron {column_count} columnas en la lista de SELECT, "
            f"se esperaba 1): {sentencia!r}"
        )
    return cleaned


def _has_top_level_semicolon(sql: str) -> bool:
    depth = 0
    in_string = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if in_string:
            if ch == "'" and not (i + 1 < n and sql[i + 1] == "'"):
                in_string = False
            elif ch == "'":
                i += 1
            i += 1
            continue
        if ch == "'":
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif ch == ";" and depth == 0:
            return True
        i += 1
    return False


def _count_select_columns(cleaned: str) -> int:
    """Cuenta las columnas de la lista de SELECT (comas de nivel superior + 1),
    considerando solo hasta el FROM de nivel superior (si existe)."""
    depth = 0
    in_string = False
    commas = 0
    i = 0
    n = len(cleaned)
    while i < n:
        ch = cleaned[i]
        if in_string:
            if ch == "'" and not (i + 1 < n and cleaned[i + 1] == "'"):
                in_string = False
            elif ch == "'":
                i += 1
            i += 1
            continue
        if ch == "'":
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
            i += 1
            continue
        if ch == ")":
            depth -= 1
            i += 1
            continue
        if depth == 0 and ch == ",":
            commas += 1
            i += 1
            continue
        if depth == 0 and _matches_word(cleaned, i, "from"):
            break
        i += 1
    return commas + 1


def _matches_word(s: str, pos: int, word: str) -> bool:
    end = pos + len(word)
    if s[pos:end].lower() != word:
        return False
    if pos > 0 and (s[pos - 1].isalnum() or s[pos - 1] == "_"):
        return False
    if end < len(s) and (s[end].isalnum() or s[end] == "_"):
        return False
    return True
