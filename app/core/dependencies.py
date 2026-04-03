from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError

from app.core.security import decode_access_token
from app.models.user import UserRole
from app.schemas.token import TokenPayload

_http_bearer = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_http_bearer),
) -> TokenPayload:
    """
    Extrae el JWT del header Authorization: Bearer <token>,
    valida su firma y expiración, y retorna el payload tipado.

    Retorna 401 si el token está expirado o tiene firma inválida.
    """
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenPayload(**payload)


def require_roles(*allowed_roles: UserRole) -> Callable[..., TokenPayload]:
    """
    Dependency factory para control de acceso basado en roles (RBAC).

    Uso:
        @router.get("/admin", dependencies=[Depends(require_roles(UserRole.ADMIN))])

    Retorna 403 si el rol del usuario no está entre los roles permitidos.
    """

    def _check_roles(
        current_user: TokenPayload = Depends(get_current_user),
    ) -> TokenPayload:
        if UserRole(current_user.role) not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permisos insuficientes",
            )
        return current_user

    return _check_roles
