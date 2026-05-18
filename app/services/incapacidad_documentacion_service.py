"""Registro de documentación faltante y transición a doc_incompleta (SCRUM-144)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado


class IncapacidadDocumentacionError(Exception):
    """Error de negocio al registrar documentación faltante."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_ESTADOS_QUE_ADMITEN_REGISTRO = frozenset(
    {
        IncapacidadEstado.EN_VERIFICACION,
        IncapacidadEstado.DOC_INCOMPLETA,
    }
)


def _normalizar_documentos(documentos: list[str]) -> list[str]:
    out: list[str] = []
    for raw in documentos:
        text = raw.strip()
        if text:
            out.append(text)
    return out


async def registrar_documentacion_faltante(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    actor_id: uuid.UUID,
    documentos: list[str],
    observacion: str | None = None,
) -> tuple[Incapacidad, IncapacidadEstado]:
    """
    Persiste la lista de documentos faltantes y deja el trámite en ``doc_incompleta``.

    Si el trámite ya está en ``doc_incompleta``, solo actualiza la lista (sin historial
    de cambio de estado). Desde ``en_verificacion`` aplica la transición y auditoría.
    """
    inc = await db.get(Incapacidad, incapacidad_id)
    if inc is None:
        raise IncapacidadDocumentacionError(404, "Incapacidad no encontrada.")

    docs = _normalizar_documentos(documentos)
    if not docs:
        raise IncapacidadDocumentacionError(
            422,
            "Debe indicar al menos un documento faltante (texto no vacío).",
        )

    prev = inc.estado
    if prev not in _ESTADOS_QUE_ADMITEN_REGISTRO:
        raise IncapacidadDocumentacionError(
            409,
            (
                "El trámite no admite registrar documentación faltante "
                "en su estado actual."
            ),
        )

    inc.documentacion_faltante = docs

    if prev == IncapacidadEstado.DOC_INCOMPLETA:
        await db.flush()
        return inc, prev

    obs = observacion.strip() if observacion and observacion.strip() else None
    if obs is None:
        obs = f"Documentación faltante: {', '.join(docs)}."

    inc.estado = IncapacidadEstado.DOC_INCOMPLETA
    db.add(
        HistorialEstado(
            incapacidad_id=inc.id,
            estado_anterior=prev,
            estado_nuevo=IncapacidadEstado.DOC_INCOMPLETA,
            user_id=actor_id,
            observacion=obs,
            timestamp=datetime.now(UTC),
        )
    )
    await db.flush()
    return inc, prev
