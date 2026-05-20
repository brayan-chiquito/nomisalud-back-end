"""Tests del control de duplicados de alertas (SCRUM-182)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.alerta_enviada import TipoAlerta
from app.services.alerta_enviada_service import (
    existe_alerta_reciente,
    registrar_alerta_enviada,
)


@pytest.mark.asyncio
async def test_existe_alerta_reciente_true() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=uuid.uuid4())
    iid = uuid.uuid4()
    ref = datetime(2026, 5, 18, 12, 0, tzinfo=UTC)
    assert await existe_alerta_reciente(
        db,
        incapacidad_id=iid,
        tipo_alerta=TipoAlerta.VENCIMIENTO_AMARILLO,
        ventana_dias=7,
        fecha_referencia=ref,
    )
    db.scalar.assert_awaited_once()


@pytest.mark.asyncio
async def test_existe_alerta_reciente_false() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    assert not await existe_alerta_reciente(
        db,
        incapacidad_id=uuid.uuid4(),
        tipo_alerta=TipoAlerta.VENCIMIENTO_ROJO,
    )


@pytest.mark.asyncio
async def test_registrar_alerta_enviada() -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    iid = uuid.uuid4()
    fila = await registrar_alerta_enviada(
        db,
        incapacidad_id=iid,
        tipo_alerta=TipoAlerta.VENCIMIENTO_AMARILLO,
        enviada_en=datetime(2026, 5, 10, tzinfo=UTC),
    )
    assert fila.incapacidad_id == iid
    assert fila.tipo_alerta == TipoAlerta.VENCIMIENTO_AMARILLO
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
