"""
Script de seed: inserta un usuario de prueba por cada rol si aún no existen.

Uso:
    python -m scripts.seed
"""

import asyncio
import sys
from pathlib import Path

# Permite ejecutar el script desde la raíz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole

SEED_USERS: list[dict] = [
    {
        "email": "colaborador@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
    },
    {
        "email": "auxiliar.rrhh@nomisalud.com",
        "password": "AuxiliarRRHH123!",
        "role": UserRole.AUXILIAR_RRHH,
    },
    {
        "email": "coordinador.rrhh@nomisalud.com",
        "password": "CoordinadorRRHH123!",
        "role": UserRole.COORDINADOR_RRHH,
    },
    {
        "email": "admin@nomisalud.com",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
    },
]


async def seed() -> None:
    # El esquema es responsabilidad de Alembic; el seed solo inserta datos.
    async with AsyncSessionLocal() as session:
        for data in SEED_USERS:
            result = await session.execute(
                select(User).where(User.email == data["email"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"[SKIP]   {data['email']} ya existe (role={existing.role.value})")
                continue

            user = User(
                email=data["email"],
                password_hash=hash_password(data["password"]),
                role=data["role"],
            )
            session.add(user)
            print(f"[INSERT] {data['email']} (role={data['role'].value})")

        await session.commit()

    print("\nSeed completado.")


if __name__ == "__main__":
    asyncio.run(seed())
