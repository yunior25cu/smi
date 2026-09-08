from pathlib import Path

import pytest

from src.excel.workbook_paths import (
    InstitutionConfig,
    InstitutionConfigError,
    get_institution,
    load_institutions,
    resolve_output_path,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_INSTITUTIONS_YAML = REPO_ROOT / "config" / "institutions.yaml"


def write_yaml(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "institutions.yaml"
    p.write_text(content, encoding="utf-8")
    return p


def test_real_institutions_yaml_loads_ok():
    configs = load_institutions(REAL_INSTITUTIONS_YAML)
    assert len(configs) == 1
    assert configs[0].id == "SMI"
    # Espacio final a propósito: es el nombre real de la hoja en el archivo.
    assert configs[0].hoja == "4315 Utilizacion "


def test_valid_yaml_loads_ok(tmp_path):
    path = write_yaml(
        tmp_path,
        "instituciones:\n"
        "  - id: SMI\n"
        "    nombre: SMI\n"
        "    plantilla: templates/SMI/plantilla.xlsx\n"
        "    hoja: DJ\n",
    )
    configs = load_institutions(path)
    assert configs == [
        InstitutionConfig(id="SMI", nombre="SMI", plantilla=Path("templates/SMI/plantilla.xlsx"), hoja="DJ")
    ]


def test_empty_instituciones_raises(tmp_path):
    path = write_yaml(tmp_path, "instituciones: []\n")
    with pytest.raises(InstitutionConfigError, match="no hay instituciones"):
        load_institutions(path)


def test_missing_instituciones_key_raises(tmp_path):
    path = write_yaml(tmp_path, "otra_cosa: 1\n")
    with pytest.raises(InstitutionConfigError, match="no hay instituciones"):
        load_institutions(path)


def test_missing_field_raises(tmp_path):
    path = write_yaml(
        tmp_path,
        "instituciones:\n  - id: SMI\n    nombre: SMI\n    hoja: DJ\n",
    )
    with pytest.raises(InstitutionConfigError, match="plantilla"):
        load_institutions(path)


def test_duplicate_id_raises(tmp_path):
    path = write_yaml(
        tmp_path,
        "instituciones:\n"
        "  - id: SMI\n    nombre: SMI\n    plantilla: a.xlsx\n    hoja: DJ\n"
        "  - id: SMI\n    nombre: SMI2\n    plantilla: b.xlsx\n    hoja: DJ\n",
    )
    with pytest.raises(InstitutionConfigError, match="duplicada"):
        load_institutions(path)


def test_get_institution_found():
    configs = [InstitutionConfig(id="SMI", nombre="SMI", plantilla=Path("a.xlsx"), hoja="DJ")]
    assert get_institution(configs, "SMI") is configs[0]


def test_get_institution_not_found_raises():
    configs = [InstitutionConfig(id="SMI", nombre="SMI", plantilla=Path("a.xlsx"), hoja="DJ")]
    with pytest.raises(InstitutionConfigError, match="OTRA"):
        get_institution(configs, "OTRA")


def test_resolve_output_path_format():
    path = resolve_output_path("SMI", 2026, 8, output_dir="output")
    assert path == Path("output") / "SMI_2026_08.xlsx"


def test_resolve_output_path_pads_month():
    path = resolve_output_path("SMI", 2026, 1)
    assert path.name == "SMI_2026_01.xlsx"
