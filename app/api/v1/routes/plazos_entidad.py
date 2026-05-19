"""CRUD admin de plazos por entidad (SCRUM-174)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.entidad_plazo import EntidadPlazo
from app.models.user import UserRole
from app.schemas.entidad_plazo import (
    EntidadPlazoCreateRequest,
    EntidadPlazoListResponse,
    EntidadPlazoResponse,
    EntidadPlazoUpdateRequest,
)
from app.services.entidad_plazo_service import (
    EntidadPlazoError,
    create_entidad_plazo,
    delete_entidad_plazo,
    get_entidad_plazo,
    list_entidad_plazos,
    update_entidad_plazo,
)

router = APIRouter(
    prefix="/admin/plazos-entidad",
    tags=["Admin — Plazos por entidad"],
)


def _to_response(row: EntidadPlazo) -> EntidadPlazoResponse:
    return EntidadPlazoResponse(
        id=row.id,
        entidad_nombre=row.entidad_nombre,
        tipo_incapacidad=row.tipo_incapacidad,
        valor_limite=row.valor_limite,
        unidad_limite=row.unidad_limite.value,
        dias_limite=row.dias_limite,
        dias_alerta=row.dias_alerta,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get(
    "",
    response_model=EntidadPlazoListResponse,
    summary="Listar plazos parametrizados",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def listar_plazos_entidad(
    db: AsyncSession = Depends(get_db),
) -> EntidadPlazoListResponse:
    rows, total = await list_entidad_plazos(db)
    return EntidadPlazoListResponse(
        items=[_to_response(row) for row in rows],
        total=total,
    )


@router.get(
    "/{plazo_id}",
    response_model=EntidadPlazoResponse,
    summary="Detalle de un plazo",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def obtener_plazo_entidad(
    plazo_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> EntidadPlazoResponse:
    row = await get_entidad_plazo(db, plazo_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plazo no encontrado."
        )
    return _to_response(row)


@router.post(
    "",
    response_model=EntidadPlazoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear plazo",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def crear_plazo_entidad(
    body: EntidadPlazoCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> EntidadPlazoResponse:
    try:
        row = await create_entidad_plazo(db, body)
        await db.commit()
        await db.refresh(row)
    except EntidadPlazoError as exc:
        await db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(row)


@router.put(
    "/{plazo_id}",
    response_model=EntidadPlazoResponse,
    summary="Actualizar plazo",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def actualizar_plazo_entidad(
    plazo_id: UUID,
    body: EntidadPlazoUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> EntidadPlazoResponse:
    row = await get_entidad_plazo(db, plazo_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plazo no encontrado."
        )
    if not body.model_dump(exclude_unset=True):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Debe enviar al menos un campo a actualizar.",
        )
    try:
        row = await update_entidad_plazo(db, row, body)
        await db.commit()
        await db.refresh(row)
    except EntidadPlazoError as exc:
        await db.rollback()
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return _to_response(row)


@router.delete(
    "/{plazo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Eliminar plazo",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def eliminar_plazo_entidad(
    plazo_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    row = await get_entidad_plazo(db, plazo_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Plazo no encontrado."
        )
    await delete_entidad_plazo(db, row)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
