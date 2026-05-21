"""Contratos API para pagos (SCRUM-185 / SCRUM-186)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

_MAX_RADICADOS = 500


class PagoCrearRequest(BaseModel):
    """Cuerpo POST /pagos: metadatos del pago y radicados cubiertos."""

    entidad_origen: str = Field(..., min_length=1, max_length=120)
    referencia: str = Field(..., min_length=1, max_length=120)
    monto: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    fecha_operacion: datetime | None = Field(
        None,
        description="Si se omite, se usa la fecha/hora actual (UTC) en el servidor.",
    )
    radicados: list[str] = Field(
        ...,
        min_length=1,
        description="Lista de radicados de incapacidades a marcar como pagadas.",
    )

    @field_validator("entidad_origen", "referencia", mode="before")
    @classmethod
    def strip_texto(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("radicados", mode="after")
    @classmethod
    def validar_radicados(cls, v: list[str]) -> list[str]:
        seen: dict[str, None] = {}
        for r in v:
            t = r.strip() if isinstance(r, str) else ""
            if not t:
                raise ValueError("Los radicados no pueden ser cadenas vacías.")
            seen[t] = None
        out = list(seen.keys())
        if len(out) > _MAX_RADICADOS:
            raise ValueError(f"Máximo {_MAX_RADICADOS} radicados por pago.")
        return out


class PagoCrearResponse(BaseModel):
    """Respuesta exitosa al registrar un pago."""

    id: uuid.UUID
    entidad_origen: str
    referencia: str
    monto: Decimal
    fecha_operacion: datetime
    radicados_asociados: list[str]


class PagoListItem(BaseModel):
    """Un pago en el listado con conteo de trámites vinculados."""

    id: uuid.UUID
    entidad_origen: str
    referencia: str
    monto: Decimal
    fecha_operacion: datetime
    estado: str
    user_id: uuid.UUID
    incapacidades_vinculadas: int = Field(
        ...,
        ge=0,
        description="Cantidad de incapacidades asociadas a este pago.",
    )


class PagoListResponse(BaseModel):
    items: list[PagoListItem]
    total: int = Field(..., ge=0)
    pages: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
