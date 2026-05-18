"""Cambio de estado de incapacidades con máquina de estados (SCRUM-137)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.services.incapacidad_transiciones import destinos_patch_validos


class IncapacidadCambioEstadoError(Exception):
    """Error de negocio al cambiar estado; el route traduce a HTTP."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def aplicar_parche_estado_incapacidad(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    actor_id: uuid.UUID,
    nuevo_estado: IncapacidadEstado,
    observacion: str | None,
) -> tuple[Incapacidad, IncapacidadEstado]:
    """
    Actualiza el estado del trámite si la transición es válida y registra historial.

    El ``timestamp`` del historial se fija en el momento de la operación (UTC).

    Returns:
        Tupla ``(incapacidad_actualizada, estado_anterior)``.
    """
    inc = await db.get(Incapacidad, incapacidad_id)
    if inc is None:
        raise IncapacidadCambioEstadoError(404, "Incapacidad no encontrada.")

    prev = inc.estado
    if prev == nuevo_estado:
        raise IncapacidadCambioEstadoError(
            400,
            "El trámite ya se encuentra en el estado solicitado.",
        )

    permitidos = destinos_patch_validos(prev)
    if nuevo_estado not in permitidos:
        raise IncapacidadCambioEstadoError(
            409,
            f"Transición no permitida de '{prev.value}' a '{nuevo_estado.value}'.",
        )

    obs = observacion.strip() if observacion and observacion.strip() else None
    if nuevo_estado == IncapacidadEstado.RECHAZADA and obs is None:
        raise IncapacidadCambioEstadoError(
            422,
            "observacion es obligatoria al pasar el trámite a rechazada.",
        )
    if obs is None:
        obs = f"Cambio de estado: {prev.value} → {nuevo_estado.value}."

    ts = datetime.now(UTC)
    inc.estado = nuevo_estado
    if nuevo_estado == IncapacidadEstado.RECHAZADA:
        inc.documentacion_faltante = [obs]
    db.add(
        HistorialEstado(
            incapacidad_id=inc.id,
            estado_anterior=prev,
            estado_nuevo=nuevo_estado,
            user_id=actor_id,
            observacion=obs,
            timestamp=ts,
        )
    )
    await db.flush()
    return inc, prev
