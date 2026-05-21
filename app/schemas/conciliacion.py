"""Contratos API de conciliación (SCRUM-189 / SCRUM-190)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ConciliacionPendienteItem(BaseModel):
    """Incapacidad cobrada sin pago liquidado asociado."""

    id: uuid.UUID
    radicado: str
    colaborador_nombre: str | None = None
    entidad_nombre: str | None = None
    incapacidad_tipo_extraido: str | None = None
    fecha_recepcion: datetime
    fecha_cobrada: datetime | None = Field(
        None,
        description="Marca temporal del historial al pasar a cobrada (si existe).",
    )


class ConciliacionDetalleIncapacidadItem(BaseModel):
    """Fila de detalle del periodo para exportación y reportes."""

    id: uuid.UUID
    radicado: str
    estado: str
    colaborador_nombre: str | None = None
    entidad_nombre: str | None = None
    incapacidad_tipo_extraido: str | None = None
    fecha_recepcion: datetime
    monto_pagado: Decimal | None = Field(
        None,
        description="Monto del pago vinculado en el periodo, si aplica.",
    )
    referencia_pago: str | None = None
    liquidado: bool = Field(
        ...,
        description="True si existe vínculo en pagos_incapacidades.",
    )


class ConciliacionResponse(BaseModel):
    """Reporte JSON de conciliación para una entidad y periodo."""

    entidad: str
    mes: int = Field(..., ge=1, le=12)
    anio: int = Field(..., ge=2000, le=2100)
    total_cobrado: Decimal = Field(
        ...,
        description=(
            "Suma de montos pagados vinculados a incapacidades cobradas en el periodo. "
            "Pendientes sin liquidar no aportan monto hasta integración de cobro "
            "externo."
        ),
    )
    total_pagado: Decimal = Field(
        ...,
        description=(
            "Suma de pagos registrados (entidad_origen + fecha_operacion en periodo)."
        ),
    )
    diferencia: Decimal = Field(
        ...,
        description=(
            "total_cobrado - total_pagado (saldo pendiente de liquidar en el periodo)."
        ),
    )
    cantidad_cobrada_periodo: int = Field(
        ...,
        ge=0,
        description="Incapacidades que pasaron a cobrada en el periodo (historial).",
    )
    cantidad_pendiente_pago: int = Field(
        ...,
        ge=0,
        description="Cobradas en el periodo sin registro en pagos_incapacidades.",
    )
    pendientes: list[ConciliacionPendienteItem]
    detalle: list[ConciliacionDetalleIncapacidadItem]


class ConciliacionResumenEntidadItem(BaseModel):
    """Fila de resumen por entidad (exportación multi-entidad)."""

    entidad: str
    total_cobrado: Decimal
    total_pagado: Decimal
    diferencia: Decimal
    cantidad_cobrada_periodo: int
    cantidad_pendiente_pago: int
