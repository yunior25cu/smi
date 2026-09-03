"""Apertura de conexión a la base MAGIK (SQL Server).

Motor y mecanismo de autenticación confirmados en la Fase 0 contra el entorno
real: Microsoft SQL Server (instancia con nombre, ej. ``Ryzen7PC\\SQLEXPRESS``),
autenticación integrada de Windows por defecto, driver ``pyodbc``.
"""

from __future__ import annotations

import logging
import os
from typing import Mapping

logger = logging.getLogger(__name__)


class ConnectionConfigError(ValueError):
    """Faltan o son inválidas las variables de entorno de conexión, o falló
    la conexión con un mensaje de bajo nivel (ODBC/driver) poco claro."""


def build_connection_string(env: Mapping[str, str]) -> str:
    """Arma la cadena de conexión ODBC a partir de variables de entorno.

    No abre conexión: es una función pura, testeable sin pyodbc ni una base
    real. Ver config/.env.example para las variables esperadas.
    """
    server = (env.get("DB_SERVER") or "").strip()
    database = (env.get("DB_DATABASE") or "").strip()
    driver = (env.get("DB_ODBC_DRIVER") or "").strip() or "ODBC Driver 17 for SQL Server"

    if not server:
        raise ConnectionConfigError("falta DB_SERVER en la configuración")
    if not database:
        raise ConnectionConfigError("falta DB_DATABASE en la configuración")

    trusted = (env.get("DB_TRUSTED_CONNECTION") or "yes").strip().lower() in (
        "yes",
        "true",
        "1",
    )

    parts = [f"DRIVER={{{driver}}}", f"SERVER={server}", f"DATABASE={database}"]
    if trusted:
        parts.append("Trusted_Connection=yes")
    else:
        user = (env.get("DB_USER") or "").strip()
        password = env.get("DB_PASSWORD") or ""
        if not user:
            raise ConnectionConfigError(
                "DB_TRUSTED_CONNECTION=no requiere DB_USER (autenticación SQL)"
            )
        parts.append(f"UID={user}")
        parts.append(f"PWD={password}")
    return ";".join(parts) + ";"


def get_connection(env: Mapping[str, str] | None = None):
    """Abre una conexión pyodbc real. Requiere pyodbc y un driver ODBC instalado.

    Si la conexión falla (servidor caído, credenciales inválidas, driver no
    instalado, etc.), envuelve el error de pyodbc -que suele venir en un
    formato de una sola línea difícil de leer- en un ConnectionConfigError
    con el servidor/base a los que se intentó conectar, sin exponer la
    contraseña.
    """
    import pyodbc

    if env is None:
        from dotenv import load_dotenv

        load_dotenv()
        env = os.environ

    conn_str = build_connection_string(env)
    server = (env.get("DB_SERVER") or "").strip()
    database = (env.get("DB_DATABASE") or "").strip()

    logger.info("conectando a SQL Server: server=%s database=%s", server, database)
    try:
        return pyodbc.connect(conn_str)
    except pyodbc.Error as exc:
        raise ConnectionConfigError(
            f"no se pudo conectar a SQL Server (server={server!r}, "
            f"database={database!r}): {exc}"
        ) from exc
