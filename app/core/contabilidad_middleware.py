"""Middleware RBAC: rol contabilidad solo en módulo financiero (SCRUM-200)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request, Response
from jose import JWTError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.security import decode_access_token
from app.models.user import UserRole

# Rutas de documentos, incapacidades y servicios de IA / recepción.
_RUTAS_DOCUMENTOS_IA = (
    "/api/v1/incapacidades",
    "/api/v1/colaboradores",
)

_MSG_CONTABILIDAD_DOCUMENTOS = (
    "El rol contabilidad no tiene acceso a documentos ni extracción por IA. "
    "Use los módulos de pagos y conciliación."
)


def _ruta_bloqueada_para_contabilidad(path: str) -> bool:
    return any(
        path == prefijo or path.startswith(f"{prefijo}/")
        for prefijo in _RUTAS_DOCUMENTOS_IA
    )


def _rol_desde_authorization(header: str | None) -> UserRole | None:
    if not header or not header.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(header[7:])
        return UserRole(payload["role"])
    except (JWTError, KeyError, ValueError):
        return None


class ContabilidadRestrictionMiddleware(BaseHTTPMiddleware):
    """
    Rechaza con 403 las peticiones del rol ``contabilidad`` hacia incapacidades
    y colaboradores (documentos / IA). El módulo financiero se autoriza en cada
    ruta con ``require_roles``.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        if _ruta_bloqueada_para_contabilidad(request.url.path):
            rol = _rol_desde_authorization(request.headers.get("Authorization"))
            if rol == UserRole.CONTABILIDAD:
                return JSONResponse(
                    status_code=403,
                    content={"detail": _MSG_CONTABILIDAD_DOCUMENTOS},
                )
        return await call_next(request)
