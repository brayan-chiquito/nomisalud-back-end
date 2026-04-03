import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import get_settings


def hash_password(plain_password: str) -> str:
    """Genera el hash bcrypt de una contraseña en texto plano."""
    return bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña en texto plano coincida con su hash bcrypt."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def decode_access_token(token: str) -> dict:
    """Decodifica y verifica la firma y expiración de un JWT.

    Lanza JWTError si el token es inválido o ExpiredSignatureError si expiró.
    """
    settings = get_settings()
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def create_access_token(user_id: uuid.UUID, role: str, email: str) -> str:
    """Genera y firma un JWT con los campos requeridos: user_id, role y email."""
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "user_id": str(user_id),
        "role": role,
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
