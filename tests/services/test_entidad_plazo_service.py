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
    delete_entidad_plazo,
    get_entidad_plazo,
    list_entidad_plazos,
    update_entidad_plazo,
)
from app.services.plazo_unidades import PlazoUnidadError


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


@pytest.mark.asyncio
async def test_create_dias_alerta_mayor_limite() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    payload = EntidadPlazoCreateRequest(
        entidad_nombre="Test",
        tipo_incapacidad="general",
        valor_limite=10,
        unidad_limite=UnidadPlazoSchema.DIAS,
        dias_alerta=20,
    )
    with pytest.raises(EntidadPlazoError) as exc:
        await create_entidad_plazo(db, payload)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_update_ok() -> None:
    row = MagicMock(spec=EntidadPlazo)
    row.id = uuid.uuid4()
    row.entidad_nombre = "A"
    row.tipo_incapacidad = "general"
    row.valor_limite = 12
    row.unidad_limite = UnidadPlazo.MESES
    row.dias_limite = 360
    row.dias_alerta = 30

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.flush = AsyncMock()

    updated = await update_entidad_plazo(
        db,
        row,
        EntidadPlazoUpdateRequest(
            valor_limite=6, unidad_limite=UnidadPlazoSchema.MESES
        ),
    )
    assert updated.valor_limite == 6
    assert updated.dias_limite == 180


@pytest.mark.asyncio
async def test_list_y_get() -> None:
    row = MagicMock(spec=EntidadPlazo)
    pid = uuid.uuid4()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=1)
    db.scalars = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[row])))
    db.get = AsyncMock(return_value=row)

    rows, total = await list_entidad_plazos(db)
    assert total == 1
    assert rows == [row]

    found = await get_entidad_plazo(db, pid)
    assert found is row


@pytest.mark.asyncio
async def test_delete() -> None:
    row = MagicMock(spec=EntidadPlazo)
    db = AsyncMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    await delete_entidad_plazo(db, row)
    db.delete.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_update_duplicado_409() -> None:
    row = MagicMock(spec=EntidadPlazo)
    row.id = uuid.uuid4()
    row.entidad_nombre = "A"
    row.tipo_incapacidad = "general"
    row.valor_limite = 1
    row.unidad_limite = UnidadPlazo.DIAS
    row.dias_limite = 1
    row.dias_alerta = 0

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=uuid.uuid4())

    with pytest.raises(EntidadPlazoError) as exc:
        await update_entidad_plazo(
            db,
            row,
            EntidadPlazoUpdateRequest(entidad_nombre="B", tipo_incapacidad="general"),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_create_plazo_unidad_error(monkeypatch) -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)

    def _boom(_valor: int, _unidad: UnidadPlazo) -> int:
        raise PlazoUnidadError("unidad inválida")

    monkeypatch.setattr(
        "app.services.entidad_plazo_service.normalizar_plazo_a_dias",
        _boom,
    )
    payload = EntidadPlazoCreateRequest(
        entidad_nombre="X",
        tipo_incapacidad="general",
        valor_limite=1,
        unidad_limite=UnidadPlazoSchema.DIAS,
        dias_alerta=0,
    )
    with pytest.raises(EntidadPlazoError) as exc:
        await create_entidad_plazo(db, payload)
    assert exc.value.status_code == 422
