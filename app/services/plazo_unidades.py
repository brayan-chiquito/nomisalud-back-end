"""Normalización de plazos a días calendario (SCRUM-173)."""

from __future__ import annotations

from app.models.entidad_plazo import UnidadPlazo

DIAS_POR_MES: int = 30
DIAS_POR_ANO: int = 365


class PlazoUnidadError(ValueError):
    """Valor o unidad de plazo inválidos."""


def normalizar_plazo_a_dias(valor: int, unidad: UnidadPlazo) -> int:
    """
    Convierte ``valor`` en la unidad indicada a días calendario enteros.

    - ``dias``: sin conversión.
    - ``meses``: 30 días por mes (parametrización interna).
    - ``anos``: 365 días por año.
    """
    if valor < 1:
        raise PlazoUnidadError("valor_limite debe ser al menos 1.")

    if unidad == UnidadPlazo.DIAS:
        return valor
    if unidad == UnidadPlazo.MESES:
        return valor * DIAS_POR_MES
    if unidad == UnidadPlazo.ANOS:
        return valor * DIAS_POR_ANO
    raise PlazoUnidadError(f"Unidad no soportada: {unidad!r}")
