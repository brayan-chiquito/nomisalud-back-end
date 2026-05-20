"""Envío SMTP de alertas con fastapi-mail (SCRUM-181)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"


@dataclass(frozen=True)
class AlertaVencimientoCorreo:
    """Datos dinámicos para la plantilla de alerta."""

    radicado: str
    colaborador_nombre: str
    entidad_nombre: str
    tipo_incapacidad: str
    dias_restantes: int
    nivel_urgencia: str


@lru_cache
def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_alerta_vencimiento_html(datos: AlertaVencimientoCorreo) -> str:
    """Compila la plantilla HTML con los datos del trámite."""
    plantilla = _jinja_env().get_template("alerta_vencimiento.html")
    return plantilla.render(
        radicado=datos.radicado,
        colaborador_nombre=datos.colaborador_nombre,
        entidad_nombre=datos.entidad_nombre,
        tipo_incapacidad=datos.tipo_incapacidad,
        dias_restantes=datos.dias_restantes,
        nivel_urgencia=datos.nivel_urgencia,
    )


def mail_configurado(settings: Settings | None = None) -> bool:
    """Indica si hay credenciales SMTP suficientes para enviar."""
    cfg = settings or get_settings()
    return bool(
        cfg.MAIL_ENABLED
        and cfg.MAIL_SERVER
        and cfg.MAIL_FROM
        and cfg.mail_alert_recipients_list
    )


def _connection_config(settings: Settings) -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        USE_CREDENTIALS=bool(settings.MAIL_USERNAME),
        VALIDATE_CERTS=settings.MAIL_VALIDATE_CERTS,
    )


async def enviar_alerta_vencimiento(
    datos: AlertaVencimientoCorreo,
    *,
    destinatarios: list[str] | None = None,
    settings: Settings | None = None,
) -> None:
    """
    Envía el correo de alerta a los destinatarios configurados.

    Raises:
        RuntimeError: si el correo no está habilitado o configurado.
    """
    cfg = settings or get_settings()
    if not mail_configurado(cfg):
        raise RuntimeError(
            "Correo no configurado: active MAIL_ENABLED y defina SMTP y destinatarios."
        )

    recipients = destinatarios or cfg.mail_alert_recipients_list
    html = render_alerta_vencimiento_html(datos)
    asunto = (
        f"[NomiSalud] Alerta vencimiento — {datos.radicado} "
        f"({datos.dias_restantes} días restantes)"
    )
    message = MessageSchema(
        subject=asunto,
        recipients=recipients,
        body=html,
        subtype=MessageType.html,
    )
    fm = FastMail(_connection_config(cfg))
    await fm.send_message(message)
    logger.info(
        "Alerta de vencimiento enviada radicado=%s destinatarios=%s",
        datos.radicado,
        recipients,
    )
