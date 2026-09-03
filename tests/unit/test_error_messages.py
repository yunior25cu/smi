from gui.error_messages import GENERIC_MESSAGE, translate
from src.core.indicator_map import IndicatorMapError
from src.db.connection import ConnectionConfigError
from src.db.dw_connection import DwConnectionNotConfiguredError
from src.db.query_builder import QueryBuilderError
from src.excel.template_writer import TemplateWriterError
from src.excel.workbook_paths import InstitutionConfigError


def test_dw_connection_not_configured_translates_to_plain_message():
    msg = translate(DwConnectionNotConfiguredError("detalle técnico interno"))
    assert "detalle técnico interno" not in msg
    assert "Avisá a sistemas" in msg


def test_connection_config_error_translates_to_plain_message():
    msg = translate(ConnectionConfigError("no se pudo conectar a SQL Server (server='x')"))
    assert "SQL Server" not in msg
    assert "conectar" in msg


def test_institution_config_error_translates():
    msg = translate(InstitutionConfigError("institución 'X' no está definida"))
    assert "'X'" not in msg
    assert "institución" in msg.lower()


def test_indicator_map_error_translates():
    msg = translate(IndicatorMapError("plasqlid 147 duplicado"))
    assert "147" not in msg
    assert "indicadores" in msg.lower()


def test_query_builder_error_translates():
    msg = translate(QueryBuilderError("plasqlid 3: PLASQLSENT no es un SELECT"))
    assert "PLASQLSENT" not in msg


def test_template_writer_error_translates():
    msg = translate(TemplateWriterError("no existe la plantilla x.xlsx"))
    assert "x.xlsx" not in msg
    assert "plantilla" in msg.lower()


def test_permission_error_translates():
    msg = translate(PermissionError("[Errno 13] Permission denied: 'out.xlsx'"))
    assert "Errno" not in msg
    assert "abierto en otro programa" in msg


def test_file_not_found_error_translates():
    msg = translate(FileNotFoundError("archivo.xlsx no existe"))
    assert "archivo.xlsx" not in msg


def test_unknown_exception_gets_generic_message():
    msg = translate(RuntimeError("algo raro que no se contempló"))
    assert msg == GENERIC_MESSAGE
    assert "algo raro" not in msg


def test_no_message_ever_leaks_a_python_traceback_marker():
    # sanity check: ningun mensaje deberia parecerse a un traceback
    for exc in (
        DwConnectionNotConfiguredError("x"),
        ConnectionConfigError("x"),
        InstitutionConfigError("x"),
        IndicatorMapError("x"),
        QueryBuilderError("x"),
        TemplateWriterError("x"),
        PermissionError("x"),
        FileNotFoundError("x"),
        RuntimeError("x"),
    ):
        msg = translate(exc)
        assert "Traceback" not in msg
        assert "File \"" not in msg
