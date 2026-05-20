"""Control de duplicados en alertas de vencimiento (SCRUM-182)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alerta_enviada import AlertaEnviada, TipoAlerta


async def existe_alerta_reciente(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    tipo_alerta: TipoAlerta,
    ventana_dias: int = 7,
    fecha_referencia: datetime | None = None,
) -> bool:
    """True si ya se envió la misma alerta en los últimos ``ventana_dias`` días."""
    ref = fecha_referencia or datetime.now(UTC)
    desde = ref - timedelta(days=ventana_dias)
    stmt = (
        select(AlertaEnviada.id)
        .where(
            AlertaEnviada.incapacidad_id == incapacidad_id,
            AlertaEnviada.tipo_alerta == tipo_alerta,
            AlertaEnviada.enviada_en >= desde,
        )
        .limit(1)
    )
    return (await db.scalar(stmt)) is not None


async def registrar_alerta_enviada(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    tipo_alerta: TipoAlerta,
    enviada_en: datetime | None = None,
) -> AlertaEnviada:
    """Persiste el historial tras un envío exitoso."""
    fila = AlertaEnviada(
        incapacidad_id=incapacidad_id,
        tipo_alerta=tipo_alerta,
        enviada_en=enviada_en or datetime.now(UTC),
    )
    db.add(fila)
    await db.flush()
    return fila
