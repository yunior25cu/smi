import pytest

import src.cli as cli
from src.cli import months_in_range, parse_args
from src.core.control_log import ControlLog
from src.excel.workbook_paths import InstitutionConfigError


def test_parses_single_month():
    args = parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "8"])
    assert args.institucion == "SMI"
    assert args.anio == 2026
    assert args.mes == 8
    assert args.desde is None


def test_parses_range():
    args = parse_args(["--institucion", "SMI", "--desde", "2026-01", "--hasta", "2026-08"])
    assert args.desde == "2026-01"
    assert args.hasta == "2026-08"


def test_missing_anio_mes_and_range_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI"])


def test_mixing_anio_mes_with_range_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "8", "--desde", "2026-01", "--hasta", "2026-08"])


def test_desde_without_hasta_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI", "--desde", "2026-01"])


def test_anio_out_of_range_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI", "--anio", "1999", "--mes", "8"])


def test_mes_out_of_range_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "13"])


def test_log_level_defaults_to_info():
    args = parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "8"])
    assert args.log_level == "INFO"


def test_log_level_can_be_overridden():
    args = parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "8", "--log-level", "DEBUG"])
    assert args.log_level == "DEBUG"


def test_invalid_log_level_errors():
    with pytest.raises(SystemExit):
        parse_args(["--institucion", "SMI", "--anio", "2026", "--mes", "8", "--log-level", "NOPE"])


def test_months_in_range_within_same_year():
    assert months_in_range("2026-06", "2026-08") == [(2026, 6), (2026, 7), (2026, 8)]


def test_months_in_range_crosses_year_boundary():
    assert months_in_range("2025-11", "2026-02") == [(2025, 11), (2025, 12), (2026, 1), (2026, 2)]


def test_months_in_range_single_month():
    assert months_in_range("2026-08", "2026-08") == [(2026, 8)]


def test_months_in_range_hasta_before_desde_raises():
    with pytest.raises(ValueError, match="anterior"):
        months_in_range("2026-08", "2026-01")


def test_months_in_range_bad_format_raises():
    with pytest.raises(ValueError, match="YYYY-MM"):
        months_in_range("2026/08", "2026-09")


def test_months_in_range_bad_month_raises():
    with pytest.raises(ValueError, match="rango"):
        months_in_range("2026-13", "2026-13")


class _FakeConn:
    def close(self):
        pass


def _fake_control_log(issues: bool) -> ControlLog:
    from src.core.indicator_map import IndicatorMapEntry

    huerfana = (IndicatorMapEntry(plasqlid=99, institucion_id="SMI", hoja="DJ", celda="F1"),)
    return ControlLog(
        institucion_id="SMI",
        anio=2026,
        mes=8,
        indicadores_sin_celda=(),
        celdas_huerfanas=huerfana if issues else (),
        indicadores_nulos=(),
    )


class _FakeResult:
    def __init__(self, output_path, issues):
        self.output_path = output_path
        self.control_log = _fake_control_log(issues)


def test_main_reports_known_errors_cleanly_with_exit_code_2(monkeypatch, capsys):
    def raise_institution_error(path):
        raise InstitutionConfigError("institución 'NOPE' no está definida")

    monkeypatch.setattr(cli, "load_institutions", raise_institution_error)

    exit_code = cli.main(["--institucion", "NOPE", "--anio", "2026", "--mes", "8"])

    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Error: institución 'NOPE' no está definida" in captured.err


def test_main_returns_0_when_no_discrepancies(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_institutions", lambda path: [])
    monkeypatch.setattr(cli, "load_indicator_map", lambda path: [])
    monkeypatch.setattr(cli, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(cli, "get_dw_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        cli,
        "run_export",
        lambda *a, **kw: _FakeResult("output/SMI_2026_08.xlsx", issues=False),
    )

    exit_code = cli.main(["--institucion", "SMI", "--anio", "2026", "--mes", "8"])
    assert exit_code == 0


def test_main_returns_1_when_control_log_has_issues(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_institutions", lambda path: [])
    monkeypatch.setattr(cli, "load_indicator_map", lambda path: [])
    monkeypatch.setattr(cli, "get_connection", lambda: _FakeConn())
    monkeypatch.setattr(cli, "get_dw_connection", lambda: _FakeConn())
    monkeypatch.setattr(
        cli,
        "run_export",
        lambda *a, **kw: _FakeResult("output/SMI_2026_08.xlsx", issues=True),
    )

    exit_code = cli.main(["--institucion", "SMI", "--anio", "2026", "--mes", "8"])
    assert exit_code == 1


def test_main_closes_connections_even_if_run_export_raises(monkeypatch):
    closed = []

    class TrackedConn(_FakeConn):
        def close(self):
            closed.append(self)

    monkeypatch.setattr(cli, "load_institutions", lambda path: [])
    monkeypatch.setattr(cli, "load_indicator_map", lambda path: [])
    monkeypatch.setattr(cli, "get_connection", lambda: TrackedConn())
    monkeypatch.setattr(cli, "get_dw_connection", lambda: TrackedConn())

    def boom(*a, **kw):
        raise RuntimeError("algo inesperado")

    monkeypatch.setattr(cli, "run_export", boom)

    with pytest.raises(RuntimeError):
        cli.main(["--institucion", "SMI", "--anio", "2026", "--mes", "8"])

    assert len(closed) == 2
