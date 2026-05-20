"""Tests del servicio SMTP y plantilla (SCRUM-181)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.mail_service import (
    AlertaVencimientoCorreo,
    enviar_alerta_vencimiento,
    mail_configurado,
    render_alerta_vencimiento_html,
)


def test_render_alerta_vencimiento_html_escapa_y_datos() -> None:
    html = render_alerta_vencimiento_html(
        AlertaVencimientoCorreo(
            radicado="IN0123456789ABCDEF0",
            colaborador_nombre="Ana <script>",
            entidad_nombre="SURA EPS",
            tipo_incapacidad="general",
            dias_restantes=5,
            nivel_urgencia="amarillo",
        )
    )
    assert "IN0123456789ABCDEF0" in html
    assert "SURA EPS" in html
    assert "5" in html
    assert "<script>" not in html
    assert "&lt;script&gt;" in html or "Ana" in html


def test_mail_configurado_requiere_campos() -> None:
    cfg = Settings(
        MAIL_ENABLED=True,
        MAIL_SERVER="smtp.test.com",
        MAIL_FROM="alertas@nomisalud.com",
        MAIL_ALERT_RECIPIENTS="rrhh@nomisalud.com",
    )
    assert mail_configurado(cfg)

    cfg_off = Settings(MAIL_ENABLED=False)
    assert not mail_configurado(cfg_off)


@pytest.mark.asyncio
async def test_enviar_alerta_vencimiento_llama_fastmail() -> None:
    cfg = Settings(
        MAIL_ENABLED=True,
        MAIL_SERVER="smtp.test.com",
        MAIL_FROM="alertas@nomisalud.com",
        MAIL_ALERT_RECIPIENTS="rrhh@nomisalud.com",
        MAIL_USERNAME="user",
        MAIL_PASSWORD="pass",
    )
    datos = AlertaVencimientoCorreo(
        radicado="IN01",
        colaborador_nombre="Juan",
        entidad_nombre="SURA EPS",
        tipo_incapacidad="general",
        dias_restantes=3,
        nivel_urgencia="amarillo",
    )
    mock_fm = MagicMock()
    mock_fm.send_message = AsyncMock()
    with patch(
        "app.services.mail_service.FastMail",
        return_value=mock_fm,
    ):
        await enviar_alerta_vencimiento(datos, settings=cfg)
    mock_fm.send_message.assert_awaited_once()
