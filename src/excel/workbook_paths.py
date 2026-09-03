"""Resuelve rutas de plantilla y de salida a partir de config/institutions.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class InstitutionConfigError(ValueError):
    """Error en config/institutions.yaml o institución no encontrada/configurada."""


@dataclass(frozen=True)
class InstitutionConfig:
    id: str
    nombre: str
    plantilla: Path
    hoja: str


def load_institutions(path: str | Path) -> list[InstitutionConfig]:
    """Carga y valida config/institutions.yaml."""
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    raw_list = data.get("instituciones")
    if not raw_list:
        raise InstitutionConfigError(
            f"{path}: no hay instituciones definidas (clave 'instituciones' vacía o ausente)"
        )

    configs: list[InstitutionConfig] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(raw_list):
        for campo in ("id", "nombre", "plantilla", "hoja"):
            if not raw.get(campo):
                raise InstitutionConfigError(f"{path}: institución #{i} no tiene '{campo}'")
        institucion_id = raw["id"]
        if institucion_id in seen_ids:
            raise InstitutionConfigError(f"{path}: institución duplicada {institucion_id!r}")
        seen_ids.add(institucion_id)
        configs.append(
            InstitutionConfig(
                id=institucion_id,
                nombre=raw["nombre"],
                plantilla=Path(raw["plantilla"]),
                hoja=raw["hoja"],
            )
        )
    return configs


def get_institution(configs: list[InstitutionConfig], institucion_id: str) -> InstitutionConfig:
    for config in configs:
        if config.id == institucion_id:
            return config
    raise InstitutionConfigError(
        f"institución {institucion_id!r} no está definida en institutions.yaml "
        f"(disponibles: {[c.id for c in configs]})"
    )


def resolve_output_path(
    institucion_id: str, anio: int, mes: int, output_dir: str | Path = "output"
) -> Path:
    return Path(output_dir) / f"{institucion_id}_{anio:04d}_{mes:02d}.xlsx"
