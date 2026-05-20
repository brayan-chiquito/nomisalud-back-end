"""Cálculo de urgencia según plazos por entidad (SCRUM-176)."""

from __future__ import annotations

import enum
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entidad_plazo import EntidadPlazo

TIPO_INCAPACIDAD_DEFAULT = "general"


class NivelUrgencia(str, enum.Enum):
    """Semáforo de urgencia para procesamiento de trámites."""

    VERDE = "verde"
    AMARILLO = "amarillo"
    ROJO = "rojo"


def _fecha_a_dia_utc(valor: datetime) -> date:
    if valor.tzinfo is None:
        return valor.date()
    return valor.astimezone(UTC).date()


def clasificar_urgencia_desde_plazo(
    *,
    fecha_recepcion: datetime,
    dias_limite: int,
    dias_alerta: int,
    fecha_evaluacion: datetime | None = None,
) -> str:
    """
      Proyecta la fecha límite y clasifica días restantes.

    - ``rojo``: vencido o sin días restantes (``dias_restantes <= 0``).
    - ``amarillo``: ventana de alerta
      (``0 < dias_restantes <= dias_alerta``).
    - ``verde``: margen cómodo antes del límite.
    """
    ref = fecha_evaluacion or datetime.now(UTC)
    fecha_limite = _fecha_a_dia_utc(fecha_recepcion) + timedelta(days=dias_limite)
    dias_restantes = (fecha_limite - _fecha_a_dia_utc(ref)).days
    if dias_restantes <= 0:
        return NivelUrgencia.ROJO.value
    if dias_restantes <= dias_alerta:
        return NivelUrgencia.AMARILLO.value
    return NivelUrgencia.VERDE.value


def _normalizar_clave(
    entidad_nombre: str | None, tipo_incapacidad: str | None
) -> tuple[str, str]:
    entidad = (entidad_nombre or "").strip().lower()
    tipo = (tipo_incapacidad or TIPO_INCAPACIDAD_DEFAULT).strip().lower()
    return entidad, tipo


async def buscar_plazo_entidad(
    db: AsyncSession,
    *,
    entidad_nombre: str | None,
    tipo_incapacidad: str | None,
) -> EntidadPlazo | None:
    """Obtiene reglas de plazo para entidad + tipo (insensible a mayúsculas)."""
    entidad, tipo = _normalizar_clave(entidad_nombre, tipo_incapacidad)
    if not entidad:
        return None

    entidad_norm = func.lower(func.trim(EntidadPlazo.entidad_nombre))
    stmt = select(EntidadPlazo).where(
        entidad_norm == entidad,
        func.lower(func.trim(EntidadPlazo.tipo_incapacidad)) == tipo,
    )
    row = await db.scalar(stmt)
    if row is not None:
        return row

    if tipo != TIPO_INCAPACIDAD_DEFAULT:
        stmt_general = select(EntidadPlazo).where(
            entidad_norm == entidad,
            func.lower(func.trim(EntidadPlazo.tipo_incapacidad))
            == TIPO_INCAPACIDAD_DEFAULT,
        )
        return await db.scalar(stmt_general)
    return None


async def cargar_indice_plazos(db: AsyncSession) -> dict[tuple[str, str], EntidadPlazo]:
    """Índice en memoria para evitar N+1 en listados."""
    filas = (await db.scalars(select(EntidadPlazo))).all()
    indice: dict[tuple[str, str], EntidadPlazo] = {}
    for fila in filas:
        clave = _normalizar_clave(fila.entidad_nombre, fila.tipo_incapacidad)
        indice[clave] = fila
    return indice


def urgencia_desde_indice(
    indice: dict[tuple[str, str], EntidadPlazo],
    *,
    fecha_recepcion: datetime,
    entidad_nombre: str | None,
    tipo_incapacidad: str | None,
    fecha_evaluacion: datetime | None = None,
) -> str:
    """Calcula urgencia usando un índice de plazos ya cargado (sin I/O)."""
    plazo = resolver_plazo_en_indice(
        indice,
        entidad_nombre=entidad_nombre,
        tipo_incapacidad=tipo_incapacidad,
    )
    if plazo is None:
        return NivelUrgencia.VERDE.value
    return clasificar_urgencia_desde_plazo(
        fecha_recepcion=fecha_recepcion,
        dias_limite=plazo.dias_limite,
        dias_alerta=plazo.dias_alerta,
        fecha_evaluacion=fecha_evaluacion,
    )


def resolver_plazo_en_indice(
    indice: dict[tuple[str, str], EntidadPlazo],
    *,
    entidad_nombre: str | None,
    tipo_incapacidad: str | None,
) -> EntidadPlazo | None:
    entidad, tipo = _normalizar_clave(entidad_nombre, tipo_incapacidad)
    if not entidad:
        return None
    if (entidad, tipo) in indice:
        return indice[(entidad, tipo)]
    if tipo != TIPO_INCAPACIDAD_DEFAULT:
        return indice.get((entidad, TIPO_INCAPACIDAD_DEFAULT))
    return None


async def calcular_urgencia(
    db: AsyncSession,
    *,
    fecha_recepcion: datetime,
    entidad_nombre: str | None,
    tipo_incapacidad: str | None,
    fecha_evaluacion: datetime | None = None,
    indice_plazos: dict[tuple[str, str], EntidadPlazo] | None = None,
) -> str:
    """
    Calcula urgencia textual para un trámite.

    Si no hay plazo configurado, devuelve ``verde``
    (sin presión de vencimiento conocida).
    """
    plazo: EntidadPlazo | None
    if indice_plazos is not None:
        plazo = resolver_plazo_en_indice(
            indice_plazos,
            entidad_nombre=entidad_nombre,
            tipo_incapacidad=tipo_incapacidad,
        )
    else:
        plazo = await buscar_plazo_entidad(
            db,
            entidad_nombre=entidad_nombre,
            tipo_incapacidad=tipo_incapacidad,
        )
    if plazo is None:
        return NivelUrgencia.VERDE.value
    return clasificar_urgencia_desde_plazo(
        fecha_recepcion=fecha_recepcion,
        dias_limite=plazo.dias_limite,
        dias_alerta=plazo.dias_alerta,
        fecha_evaluacion=fecha_evaluacion,
    )


def parse_nivel_urgencia(raw: str | None) -> str | None:
    """Valida query param de urgencia; None si no se envió."""
    if raw is None or not raw.strip():
        return None
    valor = raw.strip().lower()
    try:
        return NivelUrgencia(valor).value
    except ValueError as exc:
        raise ValueError(
            "Parámetro urgencia no es válido. Use: verde, amarillo o rojo."
        ) from exc
