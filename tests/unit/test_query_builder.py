import pytest

from src.db.catalog_repository import CatalogEntry
from src.db.query_builder import (
    QueryBuilderError,
    build_consolidated_query,
)


def entry(plasqlid, sentencia, nombre="n", descripcion="d"):
    return CatalogEntry(plasqlid=plasqlid, nombre=nombre, descripcion=descripcion, sentencia=sentencia)


def test_substitutes_placeholders_and_wraps_as_scalar_subquery():
    catalog = [entry(147, "select sum(x) from t where anio=@AAAA@ and mes=@MM@")]
    query = build_consolidated_query(catalog, 2026, 8)
    assert "2026" in query
    assert "anio=2026 and mes=8" in query
    assert "@AAAA@" not in query
    assert "@MM@" not in query
    assert "SELECT 147 AS plasqlid, (select sum(x) from t where anio=2026 and mes=8) AS valor" in query
    assert query.strip().startswith("SELECT plasqlid, valor")
    assert "UNION ALL" not in query  # un solo indicador, no hace falta unir nada


def test_multiple_entries_are_joined_with_union_all():
    catalog = [
        entry(1, "select count(*) from a"),
        entry(2, "select sum(y) from b"),
    ]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "UNION ALL" in query
    assert "SELECT 1 AS plasqlid, (select count(*) from a) AS valor" in query
    assert "SELECT 2 AS plasqlid, (select sum(y) from b) AS valor" in query


def test_trailing_semicolon_is_stripped():
    catalog = [entry(1, "select 1 from t;")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select 1 from t)" in query


def test_non_select_sentencia_raises():
    catalog = [entry(1, "update t set x=1")]
    with pytest.raises(QueryBuilderError, match="no es un SELECT"):
        build_consolidated_query(catalog, 2026, 1)


def test_multi_column_select_raises():
    catalog = [entry(1, "select a, b from t")]
    with pytest.raises(QueryBuilderError, match="2 columnas"):
        build_consolidated_query(catalog, 2026, 1)


def test_select_star_counts_as_one_column_but_is_flagged_only_if_more_present():
    # "select *" es una sola "columna" segun el conteo de comas de nivel
    # superior; sigue siendo responsabilidad de quien escribe PLASQLSENT no
    # usar select * en el catalogo real.
    catalog = [entry(1, "select * from t")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select * from t)" in query


def test_comma_inside_function_call_does_not_count_as_extra_column():
    catalog = [entry(1, "select isnull(a,b) from t")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select isnull(a,b) from t)" in query


def test_subquery_in_select_list_with_its_own_from_does_not_confuse_column_count():
    catalog = [entry(1, "select (select count(*) from t2) from t1")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select (select count(*) from t2) from t1)" in query


def test_multiple_statements_with_semicolon_in_the_middle_raises():
    catalog = [entry(1, "select 1 from t; select 2 from t2")]
    with pytest.raises(QueryBuilderError, match="más de una sentencia"):
        build_consolidated_query(catalog, 2026, 1)


def test_duplicate_plasqlid_in_catalog_raises():
    catalog = [entry(1, "select 1 from t"), entry(1, "select 2 from t")]
    with pytest.raises(QueryBuilderError, match="1 aparece más de una vez"):
        build_consolidated_query(catalog, 2026, 1)


def test_empty_catalog_raises():
    with pytest.raises(QueryBuilderError, match="vacío"):
        build_consolidated_query([], 2026, 1)


@pytest.mark.parametrize("anio", [1999, 2101, "2026", 2026.0])
def test_invalid_anio_raises(anio):
    catalog = [entry(1, "select 1 from t")]
    with pytest.raises(QueryBuilderError, match="anio"):
        build_consolidated_query(catalog, anio, 1)


@pytest.mark.parametrize("mes", [0, 13, "1", 1.0])
def test_invalid_mes_raises(mes):
    catalog = [entry(1, "select 1 from t")]
    with pytest.raises(QueryBuilderError, match="mes"):
        build_consolidated_query(catalog, 2026, mes)


def test_fhinicio_fhfin_are_substituted_with_first_and_last_day_of_month():
    catalog = [entry(1, "select count(*) from t where f >= @FHINICIO@ and f <= @FHFIN@")]
    query = build_consolidated_query(catalog, 2026, 2)  # febrero, año no bisiesto
    assert "f >= '2026-02-01' and f <= '2026-02-28'" in query


def test_fhfin_respects_leap_years():
    catalog = [entry(1, "select count(*) from t where f <= @FHFIN@")]
    query = build_consolidated_query(catalog, 2024, 2)  # 2024 es bisiesto
    assert "'2024-02-29'" in query


def test_servicios_placeholder_is_substituted_with_default_service_ids():
    # Caso real encontrado en PLACONSU: PerSerId in (@Servicios@). Confirmado
    # con el usuario: usa el mismo filtro hardcodeado en el resto del
    # catalogo, perserid in (1,101).
    catalog = [entry(3, "select sum(x) from t where perserid in (@Servicios@) and dwano=@AAAA@")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "perserid in (1,101)" in query


def test_servidios_typo_variant_is_also_substituted():
    catalog = [entry(6, "select sum(x) from t where perserid in (@Servidios@)")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "perserid in (1,101)" in query


def test_unresolved_unknown_placeholder_raises_explicit_error_instead_of_sending_broken_sql():
    catalog = [entry(1, "select sum(x) from t where perserid in (@Institucion@)")]
    with pytest.raises(QueryBuilderError, match="Institucion"):
        build_consolidated_query(catalog, 2026, 1)


def test_semicolon_inside_a_string_literal_is_not_treated_as_a_statement_separator():
    catalog = [entry(1, "select 1 from t where x = 'a;b'")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select 1 from t where x = 'a;b')" in query


def test_comma_inside_a_string_literal_is_not_counted_as_an_extra_column():
    catalog = [entry(1, "select 'a,b' from t")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select 'a,b' from t)" in query


def test_column_name_containing_the_word_from_is_not_mistaken_for_the_keyword():
    # "fromage" no es la palabra clave FROM: _matches_word tiene que
    # respetar el limite de palabra, no un simple substring.
    catalog = [entry(1, "select fromage from t")]
    query = build_consolidated_query(catalog, 2026, 1)
    assert "(select fromage from t)" in query


def test_real_placonsu_style_sentencia_is_accepted():
    sentencia = """
        select sum(dwfrcntr)
        from dwfarrec
        Where dwano = @AAAA@ and dwmes = @MM@
        AND perserid in (1,101)
        and percatid in (select percatid from clascat where ((pecriid=300 and pegcriid=45) or (pecriid=300 and pegcriid=46)))
        AND arid in (38334);
    """
    catalog = [entry(147, sentencia)]
    query = build_consolidated_query(catalog, 2026, 8)
    assert "dwano = 2026 and dwmes = 8" in query
