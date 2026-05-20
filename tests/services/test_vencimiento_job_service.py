"""Tests del job de revisión de vencimientos."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.alerta_enviada import TipoAlerta
from app.models.incapacidad import IncapacidadEstado
from app.services.vencimiento_job_service import revisar_vencimientos_y_alertar


def _incapacidad_mock(
    *,
    fecha_recepcion: datetime,
    radicado: str = "IN01",
) -> MagicMock:
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.radicado = radicado
    inc.fecha_recepcion = fecha_recepcion
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    return inc


@pytest.mark.asyncio
async def test_job_omite_si_mail_no_configurado() -> None:
    db = AsyncMock()
    with patch(
        "app.services.vencimiento_job_service.mail_configurado",
        return_value=False,
    ):
        resultado = await revisar_vencimientos_y_alertar(db)
    assert resultado.evaluados == 0
    assert resultado.alertas_enviadas == 0
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_job_envia_y_registra_sin_duplicado() -> None:
    db = AsyncMock()
    inc = _incapacidad_mock(fecha_recepcion=datetime(2025, 1, 1, tzinfo=UTC))
    mock_result = MagicMock()
    mock_result.all.return_value = [
        (inc, "María López", "SURA EPS", "general"),
    ]
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    plazo = MagicMock()
    plazo.dias_limite = 150
    plazo.dias_alerta = 15
    indice = {("sura eps", "general"): plazo}

    with (
        patch(
            "app.services.vencimiento_job_service.mail_configurado",
            return_value=True,
        ),
        patch(
            "app.services.vencimiento_job_service.cargar_indice_plazos",
            new_callable=AsyncMock,
            return_value=indice,
        ),
        patch(
            "app.services.vencimiento_job_service.existe_alerta_reciente",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "app.services.vencimiento_job_service.enviar_alerta_vencimiento",
            new_callable=AsyncMock,
        ) as send_mock,
        patch(
            "app.services.vencimiento_job_service.registrar_alerta_enviada",
            new_callable=AsyncMock,
        ) as reg_mock,
        patch(
            "app.services.vencimiento_job_service.urgencia_desde_indice",
            return_value="amarillo",
        ),
    ):
        ref = datetime(2026, 5, 18, tzinfo=UTC)
        resultado = await revisar_vencimientos_y_alertar(db, fecha_evaluacion=ref)

    assert resultado.evaluados == 1
    assert resultado.alertas_enviadas == 1
    send_mock.assert_awaited_once()
    reg_mock.assert_awaited_once()
    assert reg_mock.await_args.kwargs["tipo_alerta"] == TipoAlerta.VENCIMIENTO_AMARILLO
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_job_omite_duplicado() -> None:
    db = AsyncMock()
    inc = _incapacidad_mock(fecha_recepcion=datetime(2025, 1, 1, tzinfo=UTC))
    mock_result = MagicMock()
    mock_result.all.return_value = [(inc, "María", "SURA EPS", "general")]
    db.execute = AsyncMock(return_value=mock_result)
    db.commit = AsyncMock()

    with (
        patch(
            "app.services.vencimiento_job_service.mail_configurado",
            return_value=True,
        ),
        patch(
            "app.services.vencimiento_job_service.cargar_indice_plazos",
            new_callable=AsyncMock,
            return_value={
                ("sura eps", "general"): MagicMock(dias_limite=150, dias_alerta=15)
            },
        ),
        patch(
            "app.services.vencimiento_job_service.existe_alerta_reciente",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.services.vencimiento_job_service.enviar_alerta_vencimiento",
            new_callable=AsyncMock,
        ) as send_mock,
        patch(
            "app.services.vencimiento_job_service.urgencia_desde_indice",
            return_value="rojo",
        ),
    ):
        resultado = await revisar_vencimientos_y_alertar(db)

    assert resultado.omitidos_duplicado == 1
    assert resultado.alertas_enviadas == 0
    send_mock.assert_not_called()
