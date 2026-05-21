"""Registro y listado de pagos (SCRUM-185 / SCRUM-186)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Select, and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.pago import Pago, PagoEstado
from app.models.pago_incapacidad import PagoIncapacidad
from app.services.incapacidad_estado_service import (
    IncapacidadCambioEstadoError,
    aplicar_parche_estado_incapacidad,
)


class PagoRegistrarError(Exception):
    """Error de negocio al registrar pago."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _conds_filtros_pago(
    *,
    entidad_subcadena: str | None,
    fecha_desde: datetime | None,
    fecha_hasta: datetime | None,
    estado: PagoEstado | None,
):
    conds: list = []
    if entidad_subcadena and entidad_subcadena.strip():
        conds.append(
            Pago.entidad_origen.ilike(f"%{entidad_subcadena.strip()}%"),
        )
    if fecha_desde is not None:
        conds.append(Pago.fecha_operacion >= fecha_desde)
    if fecha_hasta is not None:
        conds.append(Pago.fecha_operacion <= fecha_hasta)
    if estado is not None:
        conds.append(Pago.estado == estado)
    return and_(*conds) if conds else true()


async def registrar_pago_y_marcar_pagadas(
    db: AsyncSession,
    *,
    entidad_origen: str,
    referencia: str,
    monto: Decimal,
    fecha_operacion: datetime | None,
    radicados: list[str],
    actor_id: uuid.UUID,
) -> Pago:
    """
    Inserta el pago, crea vínculos en ``pagos_incapacidades`` y pasa cada trámite
    de ``cobrada`` a ``pagada`` con historial.
    """
    entidad_origen = entidad_origen.strip()
    referencia = referencia.strip()
    if not radicados:
        raise PagoRegistrarError(422, "Debe indicar al menos un radicado.")

    dup = await db.scalar(
        select(Pago.id).where(
            Pago.entidad_origen == entidad_origen,
            Pago.referencia == referencia,
        )
    )
    if dup is not None:
        raise PagoRegistrarError(
            409,
            "Ya existe un pago con la misma entidad de origen y referencia.",
        )

    stmt_incs = select(Incapacidad).where(Incapacidad.radicado.in_(radicados))
    incapacidades = list((await db.execute(stmt_incs)).scalars().all())
    encontrados = {i.radicado for i in incapacidades}
    faltan = [r for r in radicados if r not in encontrados]
    if faltan:
        raise PagoRegistrarError(
            404,
            f"Radicados no encontrados: {', '.join(sorted(faltan))}",
        )

    for inc in incapacidades:
        if inc.estado != IncapacidadEstado.COBRADA:
            raise PagoRegistrarError(
                409,
                f"El trámite {inc.radicado} debe estar en estado cobrada para "
                f"registrar el pago (estado actual: {inc.estado.value}).",
            )

    ts = fecha_operacion or datetime.now(UTC)
    pago = Pago(
        entidad_origen=entidad_origen,
        referencia=referencia,
        monto=monto,
        fecha_operacion=ts,
        user_id=actor_id,
        estado=PagoEstado.REGISTRADO,
    )
    db.add(pago)
    await db.flush()

    obs = (
        f"Registro de pago ref. {referencia} ({entidad_origen}); "
        "trámite marcado como pagada."
    )
    for inc in incapacidades:
        db.add(
            PagoIncapacidad(
                pago_id=pago.id,
                incapacidad_id=inc.id,
            )
        )
        inc.pago_retrasado = False
        try:
            await aplicar_parche_estado_incapacidad(
                db,
                incapacidad_id=inc.id,
                actor_id=actor_id,
                nuevo_estado=IncapacidadEstado.PAGADA,
                observacion=obs,
            )
        except IncapacidadCambioEstadoError as e:
            raise PagoRegistrarError(e.status_code, e.detail) from e

    return pago


def _stmt_lista_pagos(where_clause) -> Select:
    """Consulta pagos con conteo de incapacidades vinculadas."""
    return (
        select(Pago, func.count(PagoIncapacidad.incapacidad_id))
        .outerjoin(
            PagoIncapacidad,
            PagoIncapacidad.pago_id == Pago.id,
        )
        .where(where_clause)
        .group_by(Pago)
    )


async def listar_pagos_paginado(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    entidad_subcadena: str | None,
    fecha_desde: datetime | None,
    fecha_hasta: datetime | None,
    estado: PagoEstado | None,
) -> tuple[list[tuple[Pago, int]], int]:
    where_clause = _conds_filtros_pago(
        entidad_subcadena=entidad_subcadena,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado,
    )

    count_base = select(func.count()).select_from(Pago).where(where_clause)
    total = int((await db.execute(count_base)).scalar_one())

    offset = (page - 1) * page_size
    stmt = (
        _stmt_lista_pagos(where_clause)
        .order_by(Pago.fecha_operacion.desc())
        .offset(offset)
        .limit(page_size)
    )
    rows = list((await db.execute(stmt)).all())
    return rows, total
