"""Tests del servicio de conciliación."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.incapacidad import IncapacidadEstado
from app.schemas.conciliacion import (
    ConciliacionResponse,
    ConciliacionResumenEntidadItem,
)
from app.services.conciliacion_periodo import rango_periodo_mes_anio
from app.services.conciliacion_service import (
    ConciliacionError,
    _cantidad_cobradas_en_periodo,
    _DatosConciliacion,
    _filtro_entidad,
    _listar_detalle_periodo,
    _listar_pendientes,
    _monto_cobrado_liquidado_periodo,
    _nombre_entidad_path,
    _sumar_pagos_periodo,
    listar_entidades_con_movimiento,
    obtener_conciliacion,
    obtener_resumen_multientidad,
)


def test_filtro_entidad_vacia() -> None:
    with pytest.raises(ConciliacionError) as exc:
        _filtro_entidad(_nombre_entidad_path(), "   ")
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_sumar_pagos_periodo() -> None:
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=1500.5)
    total = await _sumar_pagos_periodo(
        db,
        entidad="Nomi",
        periodo=rango_periodo_mes_anio(mes=6, anio=2024),
    )
    assert total == Decimal("1500.5")


@pytest.mark.asyncio
async def test_cantidad_cobradas_y_monto_liquidado() -> None:
    db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar_one.return_value = 4
    db.execute = AsyncMock(return_value=count_result)
    db.scalar = AsyncMock(return_value=200)
    periodo = rango_periodo_mes_anio(mes=6, anio=2024)
    cant = await _cantidad_cobradas_en_periodo(db, entidad="Nomi", periodo=periodo)
    monto = await _monto_cobrado_liquidado_periodo(db, entidad="Nomi", periodo=periodo)
    assert cant == 4
    assert monto == Decimal("200")


@pytest.mark.asyncio
async def test_obtener_resumen_multientidad_anio_invalido() -> None:
    db = AsyncMock()
    with pytest.raises(ConciliacionError) as exc:
        await obtener_resumen_multientidad(db, mes=1, anio=1999)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_obtener_conciliacion_mes_invalido() -> None:
    db = AsyncMock()
    with pytest.raises(ConciliacionError) as exc:
        await obtener_conciliacion(db, entidad="Nomi", mes=13, anio=2024)
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_obtener_conciliacion_ok() -> None:
    db = AsyncMock()
    with (
        patch(
            "app.services.conciliacion_service._sumar_pagos_periodo",
            new_callable=AsyncMock,
            return_value=Decimal("1000"),
        ),
        patch(
            "app.services.conciliacion_service._monto_cobrado_liquidado_periodo",
            new_callable=AsyncMock,
            return_value=Decimal("800"),
        ),
        patch(
            "app.services.conciliacion_service._cantidad_cobradas_en_periodo",
            new_callable=AsyncMock,
            return_value=3,
        ),
        patch(
            "app.services.conciliacion_service._listar_pendientes",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "app.services.conciliacion_service._listar_detalle_periodo",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        datos = await obtener_conciliacion(
            db, entidad="  NomiSalud  ", mes=5, anio=2024
        )
    assert datos.response.entidad == "NomiSalud"
    assert datos.response.total_pagado == Decimal("1000")
    assert datos.response.diferencia == Decimal("-200")
    assert datos.response.cantidad_cobrada_periodo == 3


@pytest.mark.asyncio
async def test_listar_pendientes_mapea_fila() -> None:
    db = AsyncMock()
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.radicado = "IN01"
    inc.fecha_recepcion = datetime(2024, 5, 1, tzinfo=UTC)
    result = MagicMock()
    result.all.return_value = [
        (inc, "Ana", "NomiSalud", "enfermedad", datetime(2024, 5, 2, tzinfo=UTC)),
    ]
    db.execute = AsyncMock(return_value=result)
    items = await _listar_pendientes(
        db,
        entidad="Nomi",
        periodo=rango_periodo_mes_anio(mes=5, anio=2024),
    )
    assert len(items) == 1
    assert items[0].radicado == "IN01"
    assert items[0].colaborador_nombre == "Ana"


@pytest.mark.asyncio
async def test_listar_detalle_con_monto_y_sin_liquidar() -> None:
    db = AsyncMock()
    inc_pagada = MagicMock()
    inc_pagada.id = uuid.uuid4()
    inc_pagada.radicado = "IN02"
    inc_pagada.estado = IncapacidadEstado.PAGADA
    inc_pagada.fecha_recepcion = datetime(2024, 5, 3, tzinfo=UTC)
    inc_cobrada = MagicMock()
    inc_cobrada.id = uuid.uuid4()
    inc_cobrada.radicado = "IN03"
    inc_cobrada.estado = IncapacidadEstado.COBRADA
    inc_cobrada.fecha_recepcion = datetime(2024, 5, 4, tzinfo=UTC)
    result = MagicMock()
    result.all.return_value = [
        (
            inc_pagada,
            "Juan",
            "Nomi",
            "accidente",
            Decimal("500"),
            "REF-1",
            uuid.uuid4(),
        ),
        (inc_cobrada, "Luis", "Nomi", "enf", None, None, None),
    ]
    db.execute = AsyncMock(return_value=result)
    periodo = rango_periodo_mes_anio(mes=5, anio=2024)
    items = await _listar_detalle_periodo(db, entidad="Nomi", periodo=periodo)
    assert items[0].liquidado is True
    assert items[0].monto_pagado == Decimal("500")
    assert items[1].liquidado is False
    assert items[1].monto_pagado is None


@pytest.mark.asyncio
async def test_listar_entidades_con_movimiento() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = ["  EPS A  ", "", None, "Nomi"]
    db.execute = AsyncMock(return_value=result)
    periodo = rango_periodo_mes_anio(mes=1, anio=2024)
    entidades = await listar_entidades_con_movimiento(db, periodo=periodo)
    assert entidades == ["EPS A", "Nomi"]


@pytest.mark.asyncio
async def test_obtener_resumen_multientidad() -> None:
    db = AsyncMock()
    resp = ConciliacionResponse(
        entidad="A",
        mes=1,
        anio=2024,
        total_cobrado=Decimal("1"),
        total_pagado=Decimal("1"),
        diferencia=Decimal("0"),
        cantidad_cobrada_periodo=0,
        cantidad_pendiente_pago=0,
        pendientes=[],
        detalle=[],
    )
    datos = _DatosConciliacion(
        response=resp,
        resumen_entidad=ConciliacionResumenEntidadItem(
            entidad="A",
            total_cobrado=Decimal("1"),
            total_pagado=Decimal("1"),
            diferencia=Decimal("0"),
            cantidad_cobrada_periodo=0,
            cantidad_pendiente_pago=0,
        ),
    )
    with (
        patch(
            "app.services.conciliacion_service.listar_entidades_con_movimiento",
            new_callable=AsyncMock,
            return_value=["A"],
        ),
        patch(
            "app.services.conciliacion_service.obtener_conciliacion",
            new_callable=AsyncMock,
            return_value=datos,
        ),
    ):
        resumenes, detalle = await obtener_resumen_multientidad(db, mes=1, anio=2024)
    assert len(resumenes) == 1
    assert resumenes[0].entidad == "A"
    assert detalle == []
