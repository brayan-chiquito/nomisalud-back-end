"""Verificación humana de datos extraídos (SCRUM-134)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad
from app.services.datos_extraidos_ui import enrich_datos_extraidos_for_ui
from app.services.incapacidad_transiciones import (
    ESTADO_TRAS_CONFIRMAR_VERIFICACION,
    ESTADO_TRAS_RECHAZAR_VERIFICACION,
    ESTADOS_QUE_ADMITEN_VERIFICAR,
)


class IncapacidadVerifyError(Exception):
    """Error de negocio al verificar; el route traduce a HTTP."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


async def verify_incapacidad_manual(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    actor_id: uuid.UUID,
    accion: str,
    motivo_rechazo: str | None,
    datos_extraidos: dict[str, Any] | None,
) -> Incapacidad:
    """
    Aplica confirmación o rechazo de RRHH sobre la extracción IA.

    - ``confirmar``: valida la extracción IA; deja el trámite en
      ``en_verificacion`` (desde ``en_verificacion``, ``doc_incompleta`` o
      ``procesando_ia``). Si ya estaba en ``en_verificacion``, solo actualiza
      metadatos de verificación sin duplicar historial de estado.
    - ``rechazar``: estado ``rechazada``; persiste ``motivo_rechazo`` en
      ``documentacion_faltante`` (un elemento). Para aprobar el trámite use
      ``PATCH …/estado`` con destino ``transcrita``.
    """
    stmt = (
        select(Incapacidad)
        .options(selectinload(Incapacidad.extraccion_ia))
        .where(Incapacidad.id == incapacidad_id)
    )
    inc = (await db.execute(stmt)).scalar_one_or_none()
    if inc is None:
        raise IncapacidadVerifyError(404, "Incapacidad no encontrada.")

    ext = inc.extraccion_ia
    if ext is None:
        raise IncapacidadVerifyError(
            422,
            "No hay extracción IA asociada; no se puede verificar este trámite.",
        )

    if inc.estado not in ESTADOS_QUE_ADMITEN_VERIFICAR:
        raise IncapacidadVerifyError(
            409,
            (
                "El trámite no admite verificación en su estado actual. "
                "Use PATCH /estado para transcribir, cobrar o pagar."
            ),
        )

    prev = inc.estado
    now = datetime.now(UTC)

    if accion == "confirmar":
        if datos_extraidos is not None:
            ext.datos_extraidos = enrich_datos_extraidos_for_ui(dict(datos_extraidos))
        ext.verificado_por = actor_id
        ext.verificado_en = now
        nuevo = ESTADO_TRAS_CONFIRMAR_VERIFICACION
        inc.estado = nuevo
        observacion = "Verificación manual: datos confirmados."
    elif accion == "rechazar":
        if motivo_rechazo is None or not motivo_rechazo.strip():
            raise IncapacidadVerifyError(
                422,
                "motivo_rechazo es obligatorio al rechazar.",
            )
        motivo = motivo_rechazo.strip()
        nuevo = ESTADO_TRAS_RECHAZAR_VERIFICACION
        inc.estado = nuevo
        inc.documentacion_faltante = [motivo]
        ext.verificado_por = actor_id
        ext.verificado_en = now
        observacion = f"Verificación manual: rechazado. Motivo: {motivo}"
    else:
        raise IncapacidadVerifyError(422, "accion debe ser confirmar o rechazar.")

    if prev != inc.estado:
        db.add(
            HistorialEstado(
                incapacidad_id=inc.id,
                estado_anterior=prev,
                estado_nuevo=inc.estado,
                user_id=actor_id,
                observacion=observacion,
            )
        )
    await db.flush()
    return inc
