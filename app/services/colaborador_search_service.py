"""Búsqueda de colaboradores por nombre o documento (SCRUM-197)."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


async def buscar_colaboradores(
    db: AsyncSession,
    *,
    termino: str,
    limit: int = 10,
) -> list[User]:
    """Colaboradores activos cuyo nombre o cédula coinciden parcialmente."""
    q = termino.strip()
    if not q:
        return []

    patron = f"%{q}%"
    stmt = (
        select(User)
        .where(
            User.role == UserRole.COLABORADOR,
            User.activo.is_(True),
            or_(
                User.nombre_completo.ilike(patron),
                User.numero_documento.ilike(patron),
            ),
        )
        .order_by(User.nombre_completo.asc().nulls_last())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())
