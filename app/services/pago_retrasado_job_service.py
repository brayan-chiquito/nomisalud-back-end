"""Detección diaria de pagos retrasados (SCRUM-193)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import exists, func, not_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.entidad_plazo import EntidadPlazo
from app.models.extraccion_ia import ExtraccionIA
from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.pago_incapacidad import PagoIncapacidad
from app.services.urgencia_service import (
    _fecha_a_dia_utc,
    cargar_indice_plazos,
    resolver_plazo_en_indice,
)

logger = logging.getLogger(__name__)


@dataclass
class PagoRetrasadoJobResultado:
    """Resumen auditable de la sub-rutina de pagos retrasados."""

    evaluados: int = 0
    marcados_retrasado: int = 0
    desmarcados: int = 0
    omitidos_sin_fecha_cobrada: int = 0
    errores: list[str] = field(default_factory=list)


def umbral_dias_promedio_pago(
    plazo: EntidadPlazo | None,
    *,
    settings: Settings,
) -> int:
    """Días esperados de liquidación tras cobro; default global si no hay plazo."""
    if plazo is not None and plazo.dias_promedio_pago is not None:
        return plazo.dias_promedio_pago
    return settings.PAGO_RETRASO_DIAS_DEFAULT


def dias_desde_fecha_cobrada(
    *,
    fecha_cobrada: datetime,
    fecha_evaluacion: datetime,
) -> int:
    """Días calendario transcurridos desde que el trámite pasó a cobrada."""
    return (_fecha_a_dia_utc(fecha_evaluacion) - _fecha_a_dia_utc(fecha_cobrada)).days


def evaluar_pago_retrasado(
    *,
    dias_transcurridos: int,
    umbral_dias: int,
) -> bool:
    """True si los días desde cobrada superan el umbral configurado."""
    return dias_transcurridos > umbral_dias


async def _fetch_cobradas_sin_pago(db: AsyncSession) -> list:
    nombre_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "nombre"
    )
    tipo_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "incapacidad", "tipo"
    )
    tiene_pago = (
        select(PagoIncapacidad.incapacidad_id)
        .where(PagoIncapacidad.incapacidad_id == Incapacidad.id)
        .correlate(Incapacidad)
    )
    fecha_cobrada_sq = (
        select(func.max(HistorialEstado.timestamp))
        .where(
            HistorialEstado.incapacidad_id == Incapacidad.id,
            HistorialEstado.estado_nuevo == IncapacidadEstado.COBRADA,
        )
        .correlate(Incapacidad)
        .scalar_subquery()
    )
    stmt = (
        select(
            Incapacidad,
            nombre_path,
            tipo_path,
            fecha_cobrada_sq,
        )
        .select_from(Incapacidad)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(
            Incapacidad.estado == IncapacidadEstado.COBRADA,
            not_(exists(tiene_pago)),
        )
    )
    return (await db.execute(stmt)).all()


async def _desmarcar_obsoletos(db: AsyncSession) -> int:
    """Quita la marca si el trámite ya no está cobrada pendiente o tiene pago."""
    tiene_pago = (
        select(PagoIncapacidad.incapacidad_id)
        .where(PagoIncapacidad.incapacidad_id == Incapacidad.id)
        .correlate(Incapacidad)
    )
    stmt = (
        update(Incapacidad)
        .where(
            Incapacidad.pago_retrasado.is_(True),
            ((Incapacidad.estado != IncapacidadEstado.COBRADA) | exists(tiene_pago)),
        )
        .values(pago_retrasado=False)
    )
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


async def detectar_y_marcar_pagos_retrasados(
    db: AsyncSession,
    *,
    fecha_evaluacion: datetime | None = None,
) -> PagoRetrasadoJobResultado:
    """
    Marca ``pago_retrasado`` en incapacidades cobradas sin liquidar que superan
    ``dias_promedio_pago`` de su entidad (o el default de configuración).
    """
    settings = get_settings()
    ref = fecha_evaluacion or datetime.now(UTC)
    indice_plazos = await cargar_indice_plazos(db)

    desmarcados = await _desmarcar_obsoletos(db)
    filas = await _fetch_cobradas_sin_pago(db)

    evaluados = 0
    marcados = 0
    omitidos_sin_fecha = 0

    for inc, entidad_nombre, tipo_incapacidad, fecha_cobrada in filas:
        evaluados += 1
        if fecha_cobrada is None:
            omitidos_sin_fecha += 1
            if inc.pago_retrasado:
                inc.pago_retrasado = False
            continue

        plazo = resolver_plazo_en_indice(
            indice_plazos,
            entidad_nombre=entidad_nombre,
            tipo_incapacidad=tipo_incapacidad,
        )
        umbral = umbral_dias_promedio_pago(plazo, settings=settings)
        dias = dias_desde_fecha_cobrada(
            fecha_cobrada=fecha_cobrada,
            fecha_evaluacion=ref,
        )
        debe_marcar = evaluar_pago_retrasado(
            dias_transcurridos=dias,
            umbral_dias=umbral,
        )
        if debe_marcar and not inc.pago_retrasado:
            inc.pago_retrasado = True
            marcados += 1
            logger.info(
                "Pago retrasado: radicado=%s entidad=%s dias=%s umbral=%s",
                inc.radicado,
                entidad_nombre or "?",
                dias,
                umbral,
            )
        elif not debe_marcar and inc.pago_retrasado:
            inc.pago_retrasado = False

    await db.commit()
    return PagoRetrasadoJobResultado(
        evaluados=evaluados,
        marcados_retrasado=marcados,
        desmarcados=desmarcados,
        omitidos_sin_fecha_cobrada=omitidos_sin_fecha,
    )
