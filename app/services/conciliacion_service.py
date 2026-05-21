"""Consultas de conciliación por entidad y periodo (SCRUM-189)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import Select, exists, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.extraccion_ia import ExtraccionIA
from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.pago import Pago, PagoEstado
from app.models.pago_incapacidad import PagoIncapacidad
from app.models.user import User
from app.schemas.conciliacion import (
    ConciliacionDetalleIncapacidadItem,
    ConciliacionPendienteItem,
    ConciliacionResponse,
    ConciliacionResumenEntidadItem,
)
from app.services.conciliacion_periodo import RangoPeriodo, rango_periodo_mes_anio


class ConciliacionError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass(frozen=True)
class _DatosConciliacion:
    response: ConciliacionResponse
    resumen_entidad: ConciliacionResumenEntidadItem


def _nombre_entidad_path():
    return func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "nombre"
    )


def _tipo_incapacidad_path():
    return func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "incapacidad", "tipo"
    )


def _filtro_entidad(nombre_path, entidad: str):
    entidad_norm = entidad.strip()
    if not entidad_norm:
        raise ConciliacionError(422, "entidad no puede estar vacía.")
    return nombre_path.ilike(f"%{entidad_norm}%")


async def _sumar_pagos_periodo(
    db: AsyncSession,
    *,
    entidad: str,
    periodo: RangoPeriodo,
) -> Decimal:
    entidad_norm = entidad.strip()
    stmt = select(func.coalesce(func.sum(Pago.monto), 0)).where(
        Pago.entidad_origen.ilike(f"%{entidad_norm}%"),
        Pago.fecha_operacion >= periodo.inicio,
        Pago.fecha_operacion <= periodo.fin,
        Pago.estado == PagoEstado.REGISTRADO,
    )
    valor = await db.scalar(stmt)
    return Decimal(str(valor or 0))


async def _cantidad_cobradas_en_periodo(
    db: AsyncSession,
    *,
    entidad: str,
    periodo: RangoPeriodo,
) -> int:
    nombre_path = _nombre_entidad_path()
    stmt = (
        select(func.count(func.distinct(HistorialEstado.incapacidad_id)))
        .select_from(HistorialEstado)
        .join(Incapacidad, Incapacidad.id == HistorialEstado.incapacidad_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(
            HistorialEstado.estado_nuevo == IncapacidadEstado.COBRADA,
            HistorialEstado.timestamp >= periodo.inicio,
            HistorialEstado.timestamp <= periodo.fin,
            _filtro_entidad(nombre_path, entidad),
        )
    )
    return int((await db.execute(stmt)).scalar_one() or 0)


async def _monto_cobrado_liquidado_periodo(
    db: AsyncSession,
    *,
    entidad: str,
    periodo: RangoPeriodo,
) -> Decimal:
    """Montos de pagos vinculados a incapacidades cobradas en el periodo."""
    nombre_path = _nombre_entidad_path()
    cobrada_en_periodo = (
        select(HistorialEstado.incapacidad_id)
        .where(
            HistorialEstado.estado_nuevo == IncapacidadEstado.COBRADA,
            HistorialEstado.timestamp >= periodo.inicio,
            HistorialEstado.timestamp <= periodo.fin,
        )
        .distinct()
        .subquery()
    )
    stmt = (
        select(func.coalesce(func.sum(Pago.monto), 0))
        .select_from(Pago)
        .join(PagoIncapacidad, PagoIncapacidad.pago_id == Pago.id)
        .join(Incapacidad, Incapacidad.id == PagoIncapacidad.incapacidad_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(
            Pago.estado == PagoEstado.REGISTRADO,
            Incapacidad.id.in_(select(cobrada_en_periodo.c.incapacidad_id)),
            _filtro_entidad(nombre_path, entidad),
        )
    )
    valor = await db.scalar(stmt)
    return Decimal(str(valor or 0))


def _stmt_pendientes(
    entidad: str,
    periodo: RangoPeriodo,
) -> Select:
    nombre_path = _nombre_entidad_path()
    tipo_path = _tipo_incapacidad_path()
    Colaborador = aliased(User)
    tiene_pago = (
        select(PagoIncapacidad.incapacidad_id)
        .where(PagoIncapacidad.incapacidad_id == Incapacidad.id)
        .correlate(Incapacidad)
    )
    cobrada_en_periodo = (
        select(HistorialEstado.id)
        .where(
            HistorialEstado.incapacidad_id == Incapacidad.id,
            HistorialEstado.estado_nuevo == IncapacidadEstado.COBRADA,
            HistorialEstado.timestamp >= periodo.inicio,
            HistorialEstado.timestamp <= periodo.fin,
        )
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
    return (
        select(
            Incapacidad,
            Colaborador.nombre_completo,
            nombre_path,
            tipo_path,
            fecha_cobrada_sq,
        )
        .select_from(Incapacidad)
        .join(Colaborador, Colaborador.id == Incapacidad.colaborador_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(
            Incapacidad.estado == IncapacidadEstado.COBRADA,
            not_(exists(tiene_pago)),
            exists(cobrada_en_periodo),
            _filtro_entidad(nombre_path, entidad),
        )
        .order_by(Incapacidad.fecha_recepcion.desc())
    )


async def _listar_pendientes(
    db: AsyncSession,
    *,
    entidad: str,
    periodo: RangoPeriodo,
) -> list[ConciliacionPendienteItem]:
    rows = (await db.execute(_stmt_pendientes(entidad, periodo))).all()
    out: list[ConciliacionPendienteItem] = []
    for inc, nom, en, tipo, fc in rows:
        out.append(
            ConciliacionPendienteItem(
                id=inc.id,
                radicado=inc.radicado,
                colaborador_nombre=nom,
                entidad_nombre=en,
                incapacidad_tipo_extraido=tipo,
                fecha_recepcion=inc.fecha_recepcion,
                fecha_cobrada=fc,
            )
        )
    return out


async def _listar_detalle_periodo(
    db: AsyncSession,
    *,
    entidad: str,
    periodo: RangoPeriodo,
) -> list[ConciliacionDetalleIncapacidadItem]:
    nombre_path = _nombre_entidad_path()
    tipo_path = _tipo_incapacidad_path()
    Colaborador = aliased(User)
    stmt = (
        select(
            Incapacidad,
            Colaborador.nombre_completo,
            nombre_path,
            tipo_path,
            Pago.monto,
            Pago.referencia,
            PagoIncapacidad.incapacidad_id,
        )
        .select_from(Incapacidad)
        .join(Colaborador, Colaborador.id == Incapacidad.colaborador_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .outerjoin(
            PagoIncapacidad,
            PagoIncapacidad.incapacidad_id == Incapacidad.id,
        )
        .outerjoin(Pago, Pago.id == PagoIncapacidad.pago_id)
        .where(
            Incapacidad.estado.in_(
                (IncapacidadEstado.COBRADA, IncapacidadEstado.PAGADA)
            ),
            Incapacidad.fecha_recepcion >= periodo.inicio,
            Incapacidad.fecha_recepcion <= periodo.fin,
            _filtro_entidad(nombre_path, entidad),
        )
        .order_by(Incapacidad.fecha_recepcion.desc())
    )
    rows = (await db.execute(stmt)).all()
    detalle: list[ConciliacionDetalleIncapacidadItem] = []
    for inc, nom, en, tipo, monto, ref, pi_id in rows:
        liquidado = pi_id is not None
        detalle.append(
            ConciliacionDetalleIncapacidadItem(
                id=inc.id,
                radicado=inc.radicado,
                estado=inc.estado.value,
                colaborador_nombre=nom,
                entidad_nombre=en,
                incapacidad_tipo_extraido=tipo,
                fecha_recepcion=inc.fecha_recepcion,
                monto_pagado=Decimal(str(monto)) if monto is not None else None,
                referencia_pago=ref,
                liquidado=liquidado,
            )
        )
    return detalle


async def obtener_conciliacion(
    db: AsyncSession,
    *,
    entidad: str,
    mes: int,
    anio: int,
) -> _DatosConciliacion:
    try:
        periodo = rango_periodo_mes_anio(mes=mes, anio=anio)
    except ValueError as exc:
        raise ConciliacionError(422, str(exc)) from exc

    entidad_norm = entidad.strip()
    total_pagado = await _sumar_pagos_periodo(db, entidad=entidad_norm, periodo=periodo)
    total_cobrado = await _monto_cobrado_liquidado_periodo(
        db, entidad=entidad_norm, periodo=periodo
    )
    cantidad_cobrada = await _cantidad_cobradas_en_periodo(
        db, entidad=entidad_norm, periodo=periodo
    )
    pendientes = await _listar_pendientes(db, entidad=entidad_norm, periodo=periodo)
    detalle = await _listar_detalle_periodo(db, entidad=entidad_norm, periodo=periodo)
    diferencia = total_cobrado - total_pagado

    resumen = ConciliacionResumenEntidadItem(
        entidad=entidad_norm,
        total_cobrado=total_cobrado,
        total_pagado=total_pagado,
        diferencia=diferencia,
        cantidad_cobrada_periodo=cantidad_cobrada,
        cantidad_pendiente_pago=len(pendientes),
    )
    response = ConciliacionResponse(
        entidad=entidad_norm,
        mes=periodo.mes,
        anio=periodo.anio,
        total_cobrado=total_cobrado,
        total_pagado=total_pagado,
        diferencia=diferencia,
        cantidad_cobrada_periodo=cantidad_cobrada,
        cantidad_pendiente_pago=len(pendientes),
        pendientes=pendientes,
        detalle=detalle,
    )
    return _DatosConciliacion(response=response, resumen_entidad=resumen)


async def listar_entidades_con_movimiento(
    db: AsyncSession,
    *,
    periodo: RangoPeriodo,
) -> list[str]:
    """Entidades distintas con pagos o incapacidades en el periodo."""
    nombre_path = _nombre_entidad_path()
    from_pagos = (
        select(Pago.entidad_origen.label("entidad"))
        .where(
            Pago.fecha_operacion >= periodo.inicio,
            Pago.fecha_operacion <= periodo.fin,
            Pago.estado == PagoEstado.REGISTRADO,
        )
    )
    from_incap = (
        select(nombre_path.label("entidad"))
        .select_from(Incapacidad)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(
            Incapacidad.fecha_recepcion >= periodo.inicio,
            Incapacidad.fecha_recepcion <= periodo.fin,
            nombre_path.isnot(None),
            nombre_path != "",
        )
    )
    union = from_pagos.union(from_incap).subquery()
    stmt = select(func.distinct(union.c.entidad)).order_by(union.c.entidad)
    filas = (await db.execute(stmt)).scalars().all()
    return [str(e).strip() for e in filas if e and str(e).strip()]


async def obtener_resumen_multientidad(
    db: AsyncSession,
    *,
    mes: int,
    anio: int,
) -> tuple[
    list[ConciliacionResumenEntidadItem],
    list[ConciliacionDetalleIncapacidadItem],
]:
    try:
        periodo = rango_periodo_mes_anio(mes=mes, anio=anio)
    except ValueError as exc:
        raise ConciliacionError(422, str(exc)) from exc

    entidades = await listar_entidades_con_movimiento(db, periodo=periodo)
    resumenes: list[ConciliacionResumenEntidadItem] = []
    detalle_global: list[ConciliacionDetalleIncapacidadItem] = []
    for ent in entidades:
        datos = await obtener_conciliacion(
            db, entidad=ent, mes=mes, anio=anio
        )
        resumenes.append(datos.resumen_entidad)
        detalle_global.extend(datos.response.detalle)
    return resumenes, detalle_global
