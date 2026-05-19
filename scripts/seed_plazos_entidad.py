"""
Seed de plazos por entidad (SCRUM-173).

Uso:
    python -m scripts.seed_plazos_entidad
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.entidad_plazo import EntidadPlazo, UnidadPlazo
from app.services.plazo_unidades import normalizar_plazo_a_dias

# Registros reglamentarios obligatorios (checklist SCRUM-173).
SEED_PLAZOS: list[dict] = [
    {
        "entidad_nombre": "Salud Total",
        "tipo_incapacidad": "accidente_transito",
        "valor_limite": 15,
        "unidad_limite": UnidadPlazo.DIAS,
        "dias_alerta": 3,
    },
    {
        "entidad_nombre": "SURA EPS",
        "tipo_incapacidad": "general",
        "valor_limite": 150,
        "unidad_limite": UnidadPlazo.DIAS,
        "dias_alerta": 15,
    },
    {
        "entidad_nombre": "Nueva EPS",
        "tipo_incapacidad": "general",
        "valor_limite": 12,
        "unidad_limite": UnidadPlazo.MESES,
        "dias_alerta": 30,
    },
    {
        "entidad_nombre": "SOS",
        "tipo_incapacidad": "general",
        "valor_limite": 12,
        "unidad_limite": UnidadPlazo.MESES,
        "dias_alerta": 30,
    },
    {
        "entidad_nombre": "Asmet Salud",
        "tipo_incapacidad": "general",
        "valor_limite": 12,
        "unidad_limite": UnidadPlazo.MESES,
        "dias_alerta": 30,
    },
    {
        "entidad_nombre": "Sanitas",
        "tipo_incapacidad": "general",
        "valor_limite": 3,
        "unidad_limite": UnidadPlazo.ANOS,
        "dias_alerta": 60,
    },
    {
        "entidad_nombre": "ARL SURA",
        "tipo_incapacidad": "accidente_trabajo",
        "valor_limite": 12,
        "unidad_limite": UnidadPlazo.MESES,
        "dias_alerta": 30,
    },
]


async def seed_plazos_entidad() -> None:
    async with AsyncSessionLocal() as session:
        for data in SEED_PLAZOS:
            entidad = data["entidad_nombre"]
            tipo = data["tipo_incapacidad"]
            unidad: UnidadPlazo = data["unidad_limite"]
            valor: int = data["valor_limite"]

            existing = await session.scalar(
                select(EntidadPlazo.id).where(
                    EntidadPlazo.entidad_nombre == entidad,
                    EntidadPlazo.tipo_incapacidad == tipo,
                )
            )
            if existing is not None:
                print(f"[SKIP]   {entidad} / {tipo} ya existe")
                continue

            dias_limite = normalizar_plazo_a_dias(valor, unidad)
            session.add(
                EntidadPlazo(
                    entidad_nombre=entidad,
                    tipo_incapacidad=tipo,
                    valor_limite=valor,
                    unidad_limite=unidad,
                    dias_limite=dias_limite,
                    dias_alerta=data["dias_alerta"],
                )
            )
            print(
                f"[INSERT] {entidad} / {tipo} → {valor} {unidad.value} "
                f"({dias_limite} días, alerta {data['dias_alerta']} d)"
            )

        await session.commit()

    print("\nSeed de plazos por entidad completado.")


if __name__ == "__main__":
    asyncio.run(seed_plazos_entidad())
