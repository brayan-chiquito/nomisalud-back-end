"""
Endpoints de demostración — SOLO PARA PRUEBAS DEL MIDDLEWARE DE ROLES.
Deben eliminarse antes de pasar a producción.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user, require_roles
from app.models.user import UserRole
from app.schemas.token import TokenPayload

router = APIRouter(prefix="/demo", tags=["Demo (solo pruebas)"])


@router.get(
    "/me",
    summary="[DEMO] Retorna el usuario del token",
    description="Requiere cualquier token válido. Devuelve el payload decodificado.",
)
async def get_me(current_user: TokenPayload = Depends(get_current_user)) -> dict:
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
        "role": current_user.role,
    }


@router.get(
    "/colaborador",
    summary="[DEMO] Ruta accesible por cualquier rol",
    description="Accesible por colaborador, auxiliar_rrhh, coordinador_rrhh y admin.",
    dependencies=[
        Depends(
            require_roles(
                UserRole.COLABORADOR,
                UserRole.AUXILIAR_RRHH,
                UserRole.COORDINADOR_RRHH,
                UserRole.ADMIN,
            )
        )
    ],
)
async def demo_colaborador() -> dict:
    return {"message": "Acceso concedido — rol: colaborador o superior"}


@router.get(
    "/rrhh",
    summary="[DEMO] Ruta restringida a RRHH",
    description="Accesible solo por auxiliar_rrhh, coordinador_rrhh y admin.",
    dependencies=[
        Depends(
            require_roles(
                UserRole.AUXILIAR_RRHH,
                UserRole.COORDINADOR_RRHH,
                UserRole.ADMIN,
            )
        )
    ],
)
async def demo_rrhh() -> dict:
    return {"message": "Acceso concedido — rol: auxiliar_rrhh o superior"}


@router.get(
    "/admin",
    summary="[DEMO] Ruta exclusiva para admin",
    description="Accesible únicamente por admin.",
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def demo_admin() -> dict:
    return {"message": "Acceso concedido — rol: admin"}
