"""Esquemas de plazos por entidad."""

import pytest
from pydantic import ValidationError

from app.models.entidad_plazo import UnidadPlazo
from app.schemas.entidad_plazo import (
    EntidadPlazoCreateRequest,
    EntidadPlazoUpdateRequest,
    UnidadPlazoSchema,
    unidad_schema_to_model,
)


def test_create_request_strip() -> None:
    req = EntidadPlazoCreateRequest(
        entidad_nombre="  EPS  ",
        tipo_incapacidad=" general ",
        valor_limite=1,
        unidad_limite=UnidadPlazoSchema.DIAS,
        dias_alerta=0,
    )
    assert req.entidad_nombre == "EPS"
    assert req.tipo_incapacidad == "general"


def test_create_request_vacio_invalido() -> None:
    with pytest.raises(ValidationError):
        EntidadPlazoCreateRequest(
            entidad_nombre="   ",
            tipo_incapacidad="general",
            valor_limite=1,
            unidad_limite=UnidadPlazoSchema.DIAS,
            dias_alerta=0,
        )


def test_unidad_schema_to_model() -> None:
    assert unidad_schema_to_model(UnidadPlazoSchema.ANOS) == UnidadPlazo.ANOS


def test_update_request_strip_y_none() -> None:
    assert EntidadPlazoUpdateRequest(entidad_nombre=None).entidad_nombre is None
    req = EntidadPlazoUpdateRequest(entidad_nombre="  EPS  ")
    assert req.entidad_nombre == "EPS"


def test_update_request_vacio_invalido() -> None:
    with pytest.raises(ValidationError):
        EntidadPlazoUpdateRequest(entidad_nombre="   ")
