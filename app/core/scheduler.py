"""Planificador APScheduler para tareas en segundo plano (SCRUM-180)."""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.services.pago_retrasado_job_service import detectar_y_marcar_pagos_retrasados
from app.services.vencimiento_job_service import revisar_vencimientos_y_alertar

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _ejecutar_job_vencimientos() -> None:
    """Job diario: revisión de vencimientos y envío de alertas."""
    logger.info("Inicio job diario: revisión de vencimientos")
    try:
        async with AsyncSessionLocal() as db:
            resultado = await revisar_vencimientos_y_alertar(db)
            pago_retrasado = await detectar_y_marcar_pagos_retrasados(db)
        logger.info(
            "Fin job revisión vencimientos: evaluados=%s enviados=%s "
            "duplicados_omitidos=%s verdes_omitidos=%s errores=%s",
            resultado.evaluados,
            resultado.alertas_enviadas,
            resultado.omitidos_duplicado,
            resultado.omitidos_verde,
            len(resultado.errores),
        )
        if resultado.errores:
            logger.warning("Errores parciales en job: %s", resultado.errores)
        logger.info(
            "Fin sub-rutina pagos retrasados: evaluados=%s marcados=%s "
            "desmarcados=%s sin_fecha_cobrada=%s",
            pago_retrasado.evaluados,
            pago_retrasado.marcados_retrasado,
            pago_retrasado.desmarcados,
            pago_retrasado.omitidos_sin_fecha_cobrada,
        )
    except Exception:
        logger.exception("Fallo crítico en job de revisión de vencimientos")
        raise


def iniciar_scheduler() -> AsyncIOScheduler | None:
    """
    Arranca el planificador si está habilitado en configuración.

    El job corre en el event loop asyncio (no bloquea peticiones HTTP).
    """
    global _scheduler
    settings = get_settings()
    if not settings.SCHEDULER_ENABLED:
        logger.info("APScheduler deshabilitado (SCHEDULER_ENABLED=false)")
        return None

    if _scheduler is not None:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)
    _scheduler.add_job(
        _ejecutar_job_vencimientos,
        CronTrigger(
            hour=settings.SCHEDULER_CRON_HOUR,
            minute=settings.SCHEDULER_CRON_MINUTE,
            timezone=settings.SCHEDULER_TIMEZONE,
        ),
        id="revision_vencimientos_diaria",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    _scheduler.start()
    logger.info(
        "APScheduler iniciado: job vencimientos diario a las %02d:%02d (%s)",
        settings.SCHEDULER_CRON_HOUR,
        settings.SCHEDULER_CRON_MINUTE,
        settings.SCHEDULER_TIMEZONE,
    )
    return _scheduler


def detener_scheduler() -> None:
    """Detiene el planificador en el shutdown de la aplicación."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler detenido")
        _scheduler = None
