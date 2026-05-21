"""Rutas de pagos a colaboradores (SCRUM-185 / SCRUM-186)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.pago import PagoEstado
from app.models.user import UserRole
from app.schemas.pago import (
    PagoCrearRequest,
    PagoCrearResponse,
    PagoListItem,
    PagoListResponse,
)
from app.schemas.token import TokenPayload
from app.services.incapacidad_list_service import total_pages
from app.services.pago_service import (
    PagoRegistrarError,
    listar_pagos_paginado,
    registrar_pago_y_marcar_pagadas,
)

router = APIRouter(
    prefix="/pagos",
    tags=["Pagos"],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]

_ROLES_PAGOS = (
    UserRole.AUXILIAR_RRHH,
    UserRole.COORDINADOR_RRHH,
    UserRole.ADMIN,
)


def _parse_estado_pago(raw: str | None) -> PagoEstado | None:
    if raw is None or not str(raw).strip():
        return None
    valor = str(raw).strip().lower()
    try:
        return PagoEstado(valor)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Parámetro estado debe ser registrado o anulado.",
        ) from exc


@router.post(
    "",
    response_model=PagoCrearResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar pago y marcar trámites como pagados",
)
async def crear_pago(
    body: PagoCrearRequest,
    db: DbSession,
    current_user: Annotated[
        TokenPayload,
        Depends(require_roles(*_ROLES_PAGOS)),
    ],
) -> PagoCrearResponse:
    actor = UUID(current_user.user_id)
    try:
        pago = await registrar_pago_y_marcar_pagadas(
            db,
            entidad_origen=body.entidad_origen,
            referencia=body.referencia,
            monto=body.monto,
            fecha_operacion=body.fecha_operacion,
            radicados=body.radicados,
            actor_id=actor,
        )
    except PagoRegistrarError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    return PagoCrearResponse(
        id=pago.id,
        entidad_origen=pago.entidad_origen,
        referencia=pago.referencia,
        monto=pago.monto,
        fecha_operacion=pago.fecha_operacion,
        radicados_asociados=body.radicados,
    )


@router.get(
    "",
    response_model=PagoListResponse,
    summary="Listar pagos con filtros y paginación",
)
async def listar_pagos(
    db: DbSession,
    _current_user: Annotated[
        TokenPayload,
        Depends(require_roles(*_ROLES_PAGOS)),
    ],
    page: int = Query(1, ge=1),
    entidad: str | None = Query(
        None, description="Subcadena del nombre de entidad emisora"
    ),
    fecha_desde: datetime | None = Query(
        None,
        description="Inicio del rango (inclusive)",
    ),
    fecha_hasta: datetime | None = Query(
        None,
        description="Fin del rango (inclusive)",
    ),
    estado: str | None = Query(None, description="registrado | anulado"),
) -> PagoListResponse:
    settings = get_settings()
    page_size = settings.PAGOS_PAGE_SIZE
    estado_enum = _parse_estado_pago(estado)

    rows, total = await listar_pagos_paginado(
        db,
        page=page,
        page_size=page_size,
        entidad_subcadena=entidad,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estado=estado_enum,
    )
    items = [
        PagoListItem(
            id=p.id,
            entidad_origen=p.entidad_origen,
            referencia=p.referencia,
            monto=p.monto,
            fecha_operacion=p.fecha_operacion,
            estado=p.estado.value,
            user_id=p.user_id,
            incapacidades_vinculadas=n,
        )
        for p, n in rows
    ]
    return PagoListResponse(
        items=items,
        total=total,
        pages=total_pages(total, page_size),
        page=page,
    )
