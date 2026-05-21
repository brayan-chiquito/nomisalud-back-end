"""Tests del planificador APScheduler (SCRUM-180)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.scheduler import (
    _ejecutar_job_vencimientos,
    detener_scheduler,
    iniciar_scheduler,
)
from app.services.pago_retrasado_job_service import PagoRetrasadoJobResultado
from app.services.vencimiento_job_service import VencimientoJobResultado


def test_iniciar_scheduler_deshabilitado() -> None:
    detener_scheduler()
    with patch("app.core.scheduler.get_settings") as mock_settings:
        mock_settings.return_value.SCHEDULER_ENABLED = False
        assert iniciar_scheduler() is None


def test_iniciar_scheduler_registra_job_07_00() -> None:
    detener_scheduler()
    with (
        patch("app.core.scheduler.get_settings") as mock_settings,
        patch("app.core.scheduler.AsyncIOScheduler") as mock_cls,
    ):
        s = mock_settings.return_value
        s.SCHEDULER_ENABLED = True
        s.SCHEDULER_TIMEZONE = "America/Bogota"
        s.SCHEDULER_CRON_HOUR = 7
        s.SCHEDULER_CRON_MINUTE = 0
        inst = MagicMock()
        mock_cls.return_value = inst
        iniciar_scheduler()
        inst.add_job.assert_called_once()
        call_kw = inst.add_job.call_args.kwargs
        assert call_kw["id"] == "revision_vencimientos_diaria"
        inst.start.assert_called_once()
    detener_scheduler()


@pytest.mark.asyncio
async def test_ejecutar_job_vencimientos_incluye_pagos_retrasados() -> None:
    mock_db = AsyncMock()
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_db
    mock_cm.__aexit__.return_value = None

    vencimiento = VencimientoJobResultado(evaluados=2, alertas_enviadas=1)
    pago_retrasado = PagoRetrasadoJobResultado(
        evaluados=3,
        marcados_retrasado=1,
        desmarcados=0,
        omitidos_sin_fecha_cobrada=0,
    )

    with (
        patch("app.core.scheduler.AsyncSessionLocal", return_value=mock_cm),
        patch(
            "app.core.scheduler.revisar_vencimientos_y_alertar",
            new_callable=AsyncMock,
            return_value=vencimiento,
        ) as mock_vencimiento,
        patch(
            "app.core.scheduler.detectar_y_marcar_pagos_retrasados",
            new_callable=AsyncMock,
            return_value=pago_retrasado,
        ) as mock_pago_retrasado,
    ):
        await _ejecutar_job_vencimientos()

    mock_vencimiento.assert_awaited_once_with(mock_db)
    mock_pago_retrasado.assert_awaited_once_with(mock_db)
