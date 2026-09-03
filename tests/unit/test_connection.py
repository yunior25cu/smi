import pyodbc
import pytest

from src.db.connection import ConnectionConfigError, build_connection_string, get_connection


def test_trusted_connection_string():
    env = {"DB_SERVER": r"Ryzen7PC\SQLEXPRESS", "DB_DATABASE": "MAGIK"}
    conn_str = build_connection_string(env)
    assert "SERVER=Ryzen7PC\\SQLEXPRESS" in conn_str
    assert "DATABASE=MAGIK" in conn_str
    assert "Trusted_Connection=yes" in conn_str
    assert "DRIVER={ODBC Driver 17 for SQL Server}" in conn_str
    assert "UID=" not in conn_str


def test_custom_driver_is_respected():
    env = {"DB_SERVER": "srv", "DB_DATABASE": "db", "DB_ODBC_DRIVER": "ODBC Driver 18 for SQL Server"}
    conn_str = build_connection_string(env)
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in conn_str


def test_sql_auth_connection_string():
    env = {
        "DB_SERVER": "srv",
        "DB_DATABASE": "db",
        "DB_TRUSTED_CONNECTION": "no",
        "DB_USER": "usuario",
        "DB_PASSWORD": "clave",
    }
    conn_str = build_connection_string(env)
    assert "Trusted_Connection=yes" not in conn_str
    assert "UID=usuario" in conn_str
    assert "PWD=clave" in conn_str


def test_missing_server_raises():
    with pytest.raises(ConnectionConfigError, match="DB_SERVER"):
        build_connection_string({"DB_DATABASE": "db"})


def test_missing_database_raises():
    with pytest.raises(ConnectionConfigError, match="DB_DATABASE"):
        build_connection_string({"DB_SERVER": "srv"})


def test_sql_auth_without_user_raises():
    env = {"DB_SERVER": "srv", "DB_DATABASE": "db", "DB_TRUSTED_CONNECTION": "no"}
    with pytest.raises(ConnectionConfigError, match="DB_USER"):
        build_connection_string(env)


def test_get_connection_wraps_pyodbc_errors_with_a_clear_message(monkeypatch):
    def fake_connect(conn_str):
        raise pyodbc.Error("08001", "[08001] no se pudo abrir el socket (mensaje críptico de pyodbc)")

    monkeypatch.setattr(pyodbc, "connect", fake_connect)
    env = {"DB_SERVER": "srv-inexistente", "DB_DATABASE": "db"}

    with pytest.raises(ConnectionConfigError, match="srv-inexistente") as exc_info:
        get_connection(env)
    assert "no se pudo conectar a SQL Server" in str(exc_info.value)
