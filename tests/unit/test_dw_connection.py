import pytest

from src.db.dw_connection import DwConnectionNotConfiguredError, get_dw_connection


def test_get_dw_connection_raises_a_clear_pending_implementation_error():
    with pytest.raises(DwConnectionNotConfiguredError, match="Oracle"):
        get_dw_connection()
