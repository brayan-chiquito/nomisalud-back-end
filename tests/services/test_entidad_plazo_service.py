"""Servicio CRUD de plazos por entidad (SCRUM-174)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.entidad_plazo import EntidadPlazo, UnidadPlazo
from app.schemas.entidad_plazo import (
    EntidadPlazoCreateRequest,
    EntidadPlazoUpdateRequest,
    UnidadPlazoSchema,
)
from app.services.entidad_plazo_service import (
    EntidadPlazoError,
    create_entidad_plazo,
    update_entidad_plazo,
)


@pytest.mark.asyncio
async def test_create_normaliza_meses() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()

    payload = EntidadPlazoCreateRequest(
        entidad_nombre="Nueva EPS",
        tipo_incapacidad="general",
        valor_limite=12,
        unidad_limite=UnidadPlazoSchema.MESES,
        dias_alerta=30,
    )
    row = await create_entidad_plazo(db, payload)
    assert row.dias_limite == 360
    assert row.unidad_limite == UnidadPlazo.MESES


@pytest.mark.asyncio
async def test_create_duplicado_409() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=uuid.uuid4())
    payload = EntidadPlazoCreateRequest(
        entidad_nombre="Sanitas",
        tipo_incapacidad="general",
        valor_limite=3,
        unidad_limite=UnidadPlazoSchema.ANOS,
        dias_alerta=10,
    )
    with pytest.raises(EntidadPlazoError) as exc:
        await create_entidad_plazo(db, payload)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_update_dias_alerta_mayor_que_limite_422() -> None:
    row = MagicMock(spec=EntidadPlazo)
    row.id = uuid.uuid4()
    row.entidad_nombre = "Test"
    row.tipo_incapacidad = "general"
    row.valor_limite = 15
    row.unidad_limite = UnidadPlazo.DIAS
    row.dias_limite = 15
    row.dias_alerta = 3

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()

    with pytest.raises(EntidadPlazoError) as exc:
        await update_entidad_plazo(
            db,
            row,
            EntidadPlazoUpdateRequest(dias_alerta=20),
        )
    assert exc.value.status_code == 422
