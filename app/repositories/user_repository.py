import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Retorna el usuario que coincida con el email, o None si no existe."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Retorna el usuario por id, o None si no existe."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
