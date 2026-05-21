"""
Script de seed: inserta usuarios de prueba por rol (idempotente).

Incluye colaboradores adicionales afiliados a distintas EPS/ARL para pruebas
de listados, uploads y plazos por entidad.

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
        "email": "recepcion@nomisalud.com",
        "password": "Recepcion123!",
        "role": UserRole.RECEPCION,
        "nombre_completo": "Rosa Recepción Demo",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000014",
        "area": "Recepción",
        "cargo": "Recepcionista",
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
    {
        "email": "juan.perez@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Juan Pérez García",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000005",
        "area": "Logística",
        "cargo": "Analista de operaciones",
        "eps_afiliacion": "SURA EPS",
        "arl_afiliacion": "ARL SURA",
    },
    {
        "email": "laura.martinez@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Laura Martínez Ruiz",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000006",
        "area": "Comercial",
        "cargo": "Ejecutiva de cuenta",
        "eps_afiliacion": "Nueva EPS",
        "arl_afiliacion": "ARL SURA",
    },
    {
        "email": "pedro.gomez@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Pedro Gómez López",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000007",
        "area": "Producción",
        "cargo": "Supervisor de planta",
        "eps_afiliacion": "Sanitas",
        "arl_afiliacion": "ARL Colmena",
    },
    {
        "email": "ana.torres@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Ana Torres Vargas",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000008",
        "area": "Servicios",
        "cargo": "Coordinadora de campo",
        "eps_afiliacion": "Salud Total",
        "arl_afiliacion": "ARL SURA",
    },
    {
        "email": "diego.ramirez@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Diego Ramírez Castro",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000009",
        "area": "Mantenimiento",
        "cargo": "Técnico especializado",
        "eps_afiliacion": "SOS",
        "arl_afiliacion": "ARL Positiva",
    },
    {
        "email": "carolina.diaz@nomisalud.com",
        "password": "Colaborador123!",
        "role": UserRole.COLABORADOR,
        "nombre_completo": "Carolina Díaz Moreno",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000010",
        "area": "Administración",
        "cargo": "Asistente administrativa",
        "eps_afiliacion": "Asmet Salud",
        "arl_afiliacion": "ARL SURA",
    },
    {
        "email": "auxiliar2.rrhh@nomisalud.com",
        "password": "AuxiliarRRHH123!",
        "role": UserRole.AUXILIAR_RRHH,
        "nombre_completo": "Sofía Auxiliar RRHH",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000011",
        "area": "Recursos Humanos",
        "cargo": "Auxiliar de nómina",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
    },
    {
        "email": "coordinador2.rrhh@nomisalud.com",
        "password": "CoordinadorRRHH123!",
        "role": UserRole.COORDINADOR_RRHH,
        "nombre_completo": "Luis Coordinador RRHH",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000012",
        "area": "Recursos Humanos",
        "cargo": "Coordinador de incapacidades",
        "eps_afiliacion": "EPS Salud Demo",
        "arl_afiliacion": "ARL Riesgos Demo",
    },
    {
        "email": "admin.soporte@nomisalud.com",
        "password": "Admin123!",
        "role": UserRole.ADMIN,
        "nombre_completo": "Patricia Admin Soporte",
        "tipo_documento": TipoDocumento.CC,
        "numero_documento": "1000000013",
        "area": "Tecnología",
        "cargo": "Administradora de plataforma",
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

    print("\nSeed de usuarios completado.")


async def run_all_seeds() -> None:
    await seed()
    from scripts.seed_plazos_entidad import seed_plazos_entidad

    await seed_plazos_entidad()


if __name__ == "__main__":
    asyncio.run(run_all_seeds())
