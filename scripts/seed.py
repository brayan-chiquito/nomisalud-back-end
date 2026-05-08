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
from app.models.user import TipoDocumento, User, UserRole

SEED_USERS: list[dict] = [
    {
        "email": "colaborador@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "María Colaboradora Demo",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000001",
        "area": "Operaciones",
        "cargo": "Colaborador",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
    },
    {
        "email": "auxiliar.rrhh@nomisalud.com",
        "password": "AuxiliarRRHH123!",
        "role": UserRole.AUXILIAR_RRHH,
        "nombre_completo": "Carlos Auxiliar RRHH",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000002",
        "area": "Recursos Humanos",
        "cargo": "Auxiliar RRHH",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
    },
    {
        "email": "coordinador.rrhh@nomisalud.com",
        "password": "CoordinadorRRHH123!",
        "role": UserRole.COORDINADOR_RRHH,
        "nombre_completo": "Ana Coordinadora RRHH",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000003",
        "area": "Recursos Humanos",
        "cargo": "Coordinador RRHH",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
    },
    {
        "email": "admin@nomisalud.com",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
        "nombre_completo": "Admin Sistema",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000004",
        "area": "Tecnología",
        "cargo": "Administrador",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
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
                role = existing.role.value
                print(f"[SKIP]   {data['email']} ya existe (role={role})")
                continue

            user = User(
                email=data["email"],
                password_hash=hash_password(data["password"]),
                role=data["role"],
                nombre_completo=data["nombre_completo"],
                tipo_documento=data["tipo_documento"],
                numero_documento=data["numero_documento"],
                area=data["area"],
                cargo=data["cargo"],
                eps_afiliacion=data["eps_afiliacion"],
                arl_afiliacion=data["arl_afiliacion"],
            )
            session.add(user)
            print(f"[INSERT] {data['email']} (role={data['role'].value})")

        await session.commit()

    print("\nSeed completado.")


if __name__ == "__main__":
    asyncio.run(seed())
