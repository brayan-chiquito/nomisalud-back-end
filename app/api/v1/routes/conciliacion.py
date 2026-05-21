"""Rutas de conciliación financiera (SCRUM-189 / SCRUM-190)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.schemas.conciliacion import ConciliacionResponse
from app.schemas.token import TokenPayload
from app.services.conciliacion_excel_service import generar_xlsx_conciliacion
from app.services.conciliacion_service import (
    ConciliacionError,
    obtener_conciliacion,
    obtener_resumen_multientidad,
)

router = APIRouter(
    prefix="/conciliacion",
    tags=["Conciliación"],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]

_ROLES_CONCILIACION = (
    UserRole.AUXILIAR_RRHH,
    UserRole.COORDINADOR_RRHH,
    UserRole.ADMIN,
)


def _nombre_archivo_export(mes: int, anio: int) -> str:
    return f"conciliacion_{anio}_{mes:02d}.xlsx"


@router.get(
    "",
    response_model=ConciliacionResponse,
    summary="Reporte de conciliación por entidad y periodo",
)
async def consultar_conciliacion(
    db: DbSession,
    current_user: Annotated[
        TokenPayload,
        Depends(require_roles(*_ROLES_CONCILIACION)),
    ],
    entidad: Annotated[str, Query(min_length=1, max_length=120)],
    mes: Annotated[int, Query(ge=1, le=12)],
    anio: Annotated[int, Query(ge=2000, le=2100)],
) -> ConciliacionResponse:
    del current_user
    try:
        datos = await obtener_conciliacion(db, entidad=entidad, mes=mes, anio=anio)
    except ConciliacionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return datos.response


@router.get(
    "/exportar",
    summary="Exportar conciliación a Excel (XLSX)",
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}
            }
        }
    },
)
async def exportar_conciliacion(
    db: DbSession,
    current_user: Annotated[
        TokenPayload,
        Depends(require_roles(*_ROLES_CONCILIACION)),
    ],
    mes: Annotated[int, Query(ge=1, le=12)],
    anio: Annotated[int, Query(ge=2000, le=2100)],
    entidad: Annotated[
        str | None,
        Query(
            min_length=1,
            max_length=120,
            description=(
                "Opcional. Si se omite, el resumen incluye todas las entidades "
                "con movimiento en el periodo."
            ),
        ),
    ] = None,
) -> Response:
    del current_user
    try:
        if entidad and entidad.strip():
            datos = await obtener_conciliacion(
                db,
                entidad=entidad.strip(),
                mes=mes,
                anio=anio,
            )
            resumenes = [datos.resumen_entidad]
            detalle = datos.response.detalle
        else:
            resumenes, detalle = await obtener_resumen_multientidad(
                db, mes=mes, anio=anio
            )
    except ConciliacionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    contenido = generar_xlsx_conciliacion(resumenes=resumenes, detalle=detalle)
    nombre = _nombre_archivo_export(mes, anio)
    return Response(
        content=contenido,
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
        },
        status_code=status.HTTP_200_OK,
    )
