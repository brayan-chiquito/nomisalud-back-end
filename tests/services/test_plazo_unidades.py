"""Normalización de unidades de plazo (SCRUM-173)."""

import pytest

from app.models.entidad_plazo import UnidadPlazo
from app.services.plazo_unidades import (
    DIAS_POR_ANO,
    DIAS_POR_MES,
    PlazoUnidadError,
    normalizar_plazo_a_dias,
)


def test_normalizar_dias() -> None:
    assert normalizar_plazo_a_dias(15, UnidadPlazo.DIAS) == 15


def test_normalizar_meses() -> None:
    assert normalizar_plazo_a_dias(12, UnidadPlazo.MESES) == 12 * DIAS_POR_MES


def test_normalizar_anos() -> None:
    assert normalizar_plazo_a_dias(3, UnidadPlazo.ANOS) == 3 * DIAS_POR_ANO


def test_valor_invalido() -> None:
    with pytest.raises(PlazoUnidadError):
        normalizar_plazo_a_dias(0, UnidadPlazo.DIAS)
