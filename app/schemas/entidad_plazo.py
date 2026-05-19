"""Esquemas HTTP para plazos por entidad (SCRUM-174)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator

from app.models.entidad_plazo import UnidadPlazo


class UnidadPlazoSchema(str, Enum):
    DIAS = "dias"
    MESES = "meses"
    ANOS = "anos"


class EntidadPlazoBase(BaseModel):
    entidad_nombre: str = Field(..., min_length=1, max_length=120)
    tipo_incapacidad: str = Field(..., min_length=1, max_length=80)
    valor_limite: int = Field(..., ge=1, description="Magnitud en la unidad indicada")
    unidad_limite: UnidadPlazoSchema
    dias_alerta: int = Field(
        ...,
        ge=0,
        description="Días de anticipación antes del vencimiento para alertar",
    )

    @field_validator("entidad_nombre", "tipo_incapacidad")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("No puede quedar vacío.")
        return cleaned


class EntidadPlazoCreateRequest(EntidadPlazoBase):
    pass


class EntidadPlazoUpdateRequest(BaseModel):
    entidad_nombre: str | None = Field(None, min_length=1, max_length=120)
    tipo_incapacidad: str | None = Field(None, min_length=1, max_length=80)
    valor_limite: int | None = Field(None, ge=1)
    unidad_limite: UnidadPlazoSchema | None = None
    dias_alerta: int | None = Field(None, ge=0)

    @field_validator("entidad_nombre", "tipo_incapacidad")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("No puede quedar vacío.")
        return cleaned


class EntidadPlazoResponse(BaseModel):
    id: uuid.UUID
    entidad_nombre: str
    tipo_incapacidad: str
    valor_limite: int
    unidad_limite: str
    dias_limite: int
    dias_alerta: int
    created_at: datetime
    updated_at: datetime


class EntidadPlazoListResponse(BaseModel):
    items: list[EntidadPlazoResponse]
    total: int = Field(..., ge=0)


def unidad_schema_to_model(unidad: UnidadPlazoSchema) -> UnidadPlazo:
    return UnidadPlazo(unidad.value)
