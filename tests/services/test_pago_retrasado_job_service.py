"""Tests de detección de pagos retrasados (SCRUM-193)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.models.entidad_plazo import EntidadPlazo, UnidadPlazo
from app.models.incapacidad import IncapacidadEstado
from app.services.pago_retrasado_job_service import (
    detectar_y_marcar_pagos_retrasados,
    dias_desde_fecha_cobrada,
    evaluar_pago_retrasado,
    umbral_dias_promedio_pago,
)


def test_umbral_usa_plazo_o_default() -> None:
    settings = Settings(PAGO_RETRASO_DIAS_DEFAULT=25)
    plazo = MagicMock(spec=EntidadPlazo)
    plazo.dias_promedio_pago = 15
    assert umbral_dias_promedio_pago(plazo, settings=settings) == 15
    plazo.dias_promedio_pago = None
    assert umbral_dias_promedio_pago(plazo, settings=settings) == 25
    assert umbral_dias_promedio_pago(None, settings=settings) == 25


def test_evaluar_pago_retrasado() -> None:
    assert evaluar_pago_retrasado(dias_transcurridos=31, umbral_dias=30) is True
    assert evaluar_pago_retrasado(dias_transcurridos=30, umbral_dias=30) is False


def test_dias_desde_fecha_cobrada() -> None:
    cobrada = datetime(2024, 1, 1, tzinfo=UTC)
    ref = datetime(2024, 1, 11, tzinfo=UTC)
    assert dias_desde_fecha_cobrada(fecha_cobrada=cobrada, fecha_evaluacion=ref) == 10


@pytest.mark.asyncio
async def test_detectar_marca_retrasado() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.radicado = "IN01"
    inc.estado = IncapacidadEstado.COBRADA
    inc.pago_retrasado = False
    fecha_cobrada = datetime(2024, 1, 1, tzinfo=UTC)
    plazo = EntidadPlazo(
        entidad_nombre="EPS",
        tipo_incapacidad="general",
        valor_limite=30,
        unidad_limite=UnidadPlazo.DIAS,
        dias_limite=30,
        dias_alerta=5,
        dias_promedio_pago=5,
    )
    with (
        patch(
            "app.services.pago_retrasado_job_service._desmarcar_obsoletos",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.services.pago_retrasado_job_service._fetch_cobradas_sin_pago",
            new_callable=AsyncMock,
            return_value=[(inc, "EPS", "general", fecha_cobrada)],
        ),
        patch(
            "app.services.pago_retrasado_job_service.cargar_indice_plazos",
            new_callable=AsyncMock,
            return_value={("eps", "general"): plazo},
        ),
        patch(
            "app.services.pago_retrasado_job_service.get_settings",
            return_value=Settings(PAGO_RETRASO_DIAS_DEFAULT=30),
        ),
    ):
        resultado = await detectar_y_marcar_pagos_retrasados(
            db,
            fecha_evaluacion=datetime(2024, 1, 20, tzinfo=UTC),
        )
    assert resultado.marcados_retrasado == 1
    assert inc.pago_retrasado is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_detectar_desmarca_si_ya_no_retrasado() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    inc = MagicMock()
    inc.pago_retrasado = True
    fecha_cobrada = datetime(2024, 1, 19, tzinfo=UTC)
    with (
        patch(
            "app.services.pago_retrasado_job_service._desmarcar_obsoletos",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch(
            "app.services.pago_retrasado_job_service._fetch_cobradas_sin_pago",
            new_callable=AsyncMock,
            return_value=[(inc, "EPS", "general", fecha_cobrada)],
        ),
        patch(
            "app.services.pago_retrasado_job_service.cargar_indice_plazos",
            new_callable=AsyncMock,
            return_value={},
        ),
        patch(
            "app.services.pago_retrasado_job_service.get_settings",
            return_value=Settings(PAGO_RETRASO_DIAS_DEFAULT=30),
        ),
        patch(
            "app.services.pago_retrasado_job_service.resolver_plazo_en_indice",
            return_value=None,
        ),
    ):
        resultado = await detectar_y_marcar_pagos_retrasados(
            db,
            fecha_evaluacion=datetime(2024, 1, 20, tzinfo=UTC),
        )
    assert resultado.marcados_retrasado == 0
    assert inc.pago_retrasado is False


@pytest.mark.asyncio
async def test_detectar_sin_fecha_cobrada_limpia_marca() -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    inc = MagicMock()
    inc.pago_retrasado = True
    with (
        patch(
            "app.services.pago_retrasado_job_service._desmarcar_obsoletos",
            new_callable=AsyncMock,
            return_value=2,
        ),
        patch(
            "app.services.pago_retrasado_job_service._fetch_cobradas_sin_pago",
            new_callable=AsyncMock,
            return_value=[(inc, "E", "general", None)],
        ),
        patch(
            "app.services.pago_retrasado_job_service.cargar_indice_plazos",
            new_callable=AsyncMock,
            return_value={},
        ),
    ):
        resultado = await detectar_y_marcar_pagos_retrasados(db)
    assert resultado.omitidos_sin_fecha_cobrada == 1
    assert resultado.desmarcados == 2
    assert inc.pago_retrasado is False


@pytest.mark.asyncio
async def test_desmarcar_obsoletos_retorna_rowcount() -> None:
    from app.services.pago_retrasado_job_service import _desmarcar_obsoletos

    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 3
    db.execute = AsyncMock(return_value=mock_result)
    n = await _desmarcar_obsoletos(db)
    assert n == 3
