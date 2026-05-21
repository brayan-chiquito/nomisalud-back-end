"""CRUD de plazos por entidad (SCRUM-174)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entidad_plazo import EntidadPlazo, UnidadPlazo
from app.schemas.entidad_plazo import (
    EntidadPlazoCreateRequest,
    EntidadPlazoUpdateRequest,
    unidad_schema_to_model,
)
from app.services.plazo_unidades import PlazoUnidadError, normalizar_plazo_a_dias


class EntidadPlazoError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _to_unidad_model(unidad: UnidadPlazo | str) -> UnidadPlazo:
    if isinstance(unidad, UnidadPlazo):
        return unidad
    return UnidadPlazo(unidad)


async def list_entidad_plazos(db: AsyncSession) -> tuple[list[EntidadPlazo], int]:
    total = await db.scalar(select(func.count()).select_from(EntidadPlazo)) or 0
    rows = (
        await db.scalars(
            select(EntidadPlazo).order_by(
                EntidadPlazo.entidad_nombre.asc(),
                EntidadPlazo.tipo_incapacidad.asc(),
            )
        )
    ).all()
    return list(rows), int(total)


async def get_entidad_plazo(
    db: AsyncSession, plazo_id: uuid.UUID
) -> EntidadPlazo | None:
    return await db.get(EntidadPlazo, plazo_id)


async def _exists_entidad_tipo(
    db: AsyncSession,
    *,
    entidad_nombre: str,
    tipo_incapacidad: str,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(EntidadPlazo.id).where(
        EntidadPlazo.entidad_nombre == entidad_nombre,
        EntidadPlazo.tipo_incapacidad == tipo_incapacidad,
    )
    if exclude_id is not None:
        stmt = stmt.where(EntidadPlazo.id != exclude_id)
    existing = await db.scalar(stmt)
    return existing is not None


async def create_entidad_plazo(
    db: AsyncSession,
    payload: EntidadPlazoCreateRequest,
) -> EntidadPlazo:
    unidad = unidad_schema_to_model(payload.unidad_limite)
    try:
        dias_limite = normalizar_plazo_a_dias(payload.valor_limite, unidad)
    except PlazoUnidadError as exc:
        raise EntidadPlazoError(422, str(exc)) from exc

    if await _exists_entidad_tipo(
        db,
        entidad_nombre=payload.entidad_nombre,
        tipo_incapacidad=payload.tipo_incapacidad,
    ):
        raise EntidadPlazoError(
            409,
            "Ya existe un plazo para esa entidad y tipo de incapacidad.",
        )

    if payload.dias_alerta > dias_limite:
        raise EntidadPlazoError(
            422,
            "dias_alerta no puede ser mayor que dias_limite.",
        )

    row = EntidadPlazo(
        entidad_nombre=payload.entidad_nombre,
        tipo_incapacidad=payload.tipo_incapacidad,
        valor_limite=payload.valor_limite,
        unidad_limite=unidad,
        dias_limite=dias_limite,
        dias_alerta=payload.dias_alerta,
        dias_promedio_pago=payload.dias_promedio_pago,
    )
    db.add(row)
    await db.flush()
    return row


async def update_entidad_plazo(
    db: AsyncSession,
    row: EntidadPlazo,
    payload: EntidadPlazoUpdateRequest,
) -> EntidadPlazo:
    entidad = (
        payload.entidad_nombre
        if payload.entidad_nombre is not None
        else row.entidad_nombre
    )
    tipo = (
        payload.tipo_incapacidad
        if payload.tipo_incapacidad is not None
        else row.tipo_incapacidad
    )
    valor = (
        payload.valor_limite if payload.valor_limite is not None else row.valor_limite
    )
    unidad = (
        unidad_schema_to_model(payload.unidad_limite)
        if payload.unidad_limite is not None
        else row.unidad_limite
    )
    dias_alerta = (
        payload.dias_alerta if payload.dias_alerta is not None else row.dias_alerta
    )
    dias_promedio_pago = (
        payload.dias_promedio_pago
        if payload.dias_promedio_pago is not None
        else row.dias_promedio_pago
    )

    try:
        dias_limite = normalizar_plazo_a_dias(valor, unidad)
    except PlazoUnidadError as exc:
        raise EntidadPlazoError(422, str(exc)) from exc

    if await _exists_entidad_tipo(
        db,
        entidad_nombre=entidad,
        tipo_incapacidad=tipo,
        exclude_id=row.id,
    ):
        raise EntidadPlazoError(
            409,
            "Ya existe un plazo para esa entidad y tipo de incapacidad.",
        )

    if dias_alerta > dias_limite:
        raise EntidadPlazoError(
            422,
            "dias_alerta no puede ser mayor que dias_limite.",
        )

    row.entidad_nombre = entidad
    row.tipo_incapacidad = tipo
    row.valor_limite = valor
    row.unidad_limite = unidad
    row.dias_limite = dias_limite
    row.dias_alerta = dias_alerta
    row.dias_promedio_pago = dias_promedio_pago
    await db.flush()
    return row


async def delete_entidad_plazo(db: AsyncSession, row: EntidadPlazo) -> None:
    await db.delete(row)
    await db.flush()
