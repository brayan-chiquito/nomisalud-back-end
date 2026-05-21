"""Tests del servicio de pagos."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.incapacidad import IncapacidadEstado
from app.services.pago_service import (
    PagoRegistrarError,
    listar_pagos_paginado,
    registrar_pago_y_marcar_pagadas,
)


@pytest.mark.asyncio
async def test_registrar_pago_radico_no_encontrado() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    with pytest.raises(PagoRegistrarError) as exc:
        await registrar_pago_y_marcar_pagadas(
            db,
            entidad_origen=" EPS X ",
            referencia="REF1",
            monto=Decimal("100.00"),
            fecha_operacion=datetime(2026, 1, 1, tzinfo=UTC),
            radicados=["INNOEXISTE"],
            actor_id=uuid.uuid4(),
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_registrar_duplicado_entidad_referencia() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=uuid.uuid4())
    with pytest.raises(PagoRegistrarError) as exc:
        await registrar_pago_y_marcar_pagadas(
            db,
            entidad_origen="E",
            referencia="R",
            monto=Decimal("1.00"),
            fecha_operacion=None,
            radicados=["IN1"],
            actor_id=uuid.uuid4(),
        )
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_listar_pagos_vacio() -> None:
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    list_result = MagicMock()
    list_result.all.return_value = []
    db.execute = AsyncMock(side_effect=[count_result, list_result])
    rows, total = await listar_pagos_paginado(
        db,
        page=1,
        page_size=10,
        entidad_subcadena=None,
        fecha_desde=None,
        fecha_hasta=None,
        estado=None,
    )
    assert total == 0
    assert rows == []


@pytest.mark.asyncio
async def test_registrar_pago_limpia_pago_retrasado() -> None:
    actor_id = uuid.uuid4()
    inc_id = uuid.uuid4()
    inc = MagicMock()
    inc.id = inc_id
    inc.radicado = "IN1"
    inc.estado = IncapacidadEstado.COBRADA
    inc.pago_retrasado = True

    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    db.add = MagicMock()
    db.flush = AsyncMock()

    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [inc]
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.pago_service.aplicar_parche_estado_incapacidad",
        new_callable=AsyncMock,
    ):
        pago = await registrar_pago_y_marcar_pagadas(
            db,
            entidad_origen="EPS",
            referencia="REF-1",
            monto=Decimal("50000.00"),
            fecha_operacion=datetime(2026, 1, 15, tzinfo=UTC),
            radicados=["IN1"],
            actor_id=actor_id,
        )

    assert inc.pago_retrasado is False
    assert pago.entidad_origen == "EPS"
    db.flush.assert_awaited_once()
