"""Búsqueda de colaboradores para recepción y RRHH (SCRUM-197)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.schemas.colaborador import ColaboradorBusquedaItem, ColaboradorBusquedaResponse
from app.schemas.token import TokenPayload
from app.services.colaborador_search_service import buscar_colaboradores

router = APIRouter(prefix="/colaboradores", tags=["Colaboradores"])

DbSession = Annotated[AsyncSession, Depends(get_db)]
_BuscarColaboradoresUser = Annotated[
    TokenPayload,
    Depends(
        require_roles(
            UserRole.RECEPCION,
            UserRole.AUXILIAR_RRHH,
            UserRole.COORDINADOR_RRHH,
            UserRole.ADMIN,
        )
    ),
]


@router.get(
    "/buscar",
    response_model=ColaboradorBusquedaResponse,
    summary="Autocompletado de colaboradores",
    description=(
        "Busca colaboradores activos por subcadena en nombre completo o número "
        "de documento (cédula). Pensado para el selector de recepción (SCRUM-197)."
    ),
)
async def buscar_colaboradores_endpoint(
    _current_user: _BuscarColaboradoresUser,
    db: DbSession,
    q: str = Query(
        "",
        min_length=0,
        max_length=100,
        description="Texto de búsqueda (nombre o cédula)",
    ),
    limit: int = Query(10, ge=1, le=50),
) -> ColaboradorBusquedaResponse:
    rows = await buscar_colaboradores(db, termino=q, limit=limit)
    return ColaboradorBusquedaResponse(
        items=[
            ColaboradorBusquedaItem(
                id=u.id,
                nombre_completo=u.nombre_completo,
                numero_documento=u.numero_documento,
                email=u.email,
            )
            for u in rows
        ]
    )
