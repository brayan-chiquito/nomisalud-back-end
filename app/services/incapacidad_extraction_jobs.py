"""Tareas en segundo plano: extracción IA tras carga de incapacidad (SCRUM-127)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import AsyncSessionLocal
from app.models.extraccion_ia import ExtraccionIA
from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.services.ai_extractor import GeminiExtractionError, extract_from_local_file
from app.services.datos_extraidos_ui import enrich_datos_extraidos_for_ui
from app.services.ocr_processor import OcrProcessorError, procesar_documento

logger = logging.getLogger(__name__)

_MAX_RAW_RESPONSE_DB_CHARS: int = 512_000

_DATOS_KEYS = (
    "paciente",
    "incapacidad",
    "diagnostico",
    "entidad",
    "medico",
    "documento",
)


def _split_extraccion_payload(
    result: dict[str, object | None],
) -> tuple[dict[str, object | None], dict[str, object | None] | None]:
    datos = {k: result.get(k) for k in _DATOS_KEYS}
    raw_val = result.get("validaciones")
    validaciones = raw_val if isinstance(raw_val, dict) else None
    return datos, validaciones


def _truncate_raw_for_db(text: str) -> str:
    if len(text) <= _MAX_RAW_RESPONSE_DB_CHARS:
        return text
    limit = _MAX_RAW_RESPONSE_DB_CHARS - 30
    return f"{text[:limit]}\n...[truncado para almacenamiento]"


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, GeminiExtractionError):
        return str(exc)
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, FileNotFoundError):
        return "Archivo no encontrado."
    return f"Error en extracción: {type(exc).__name__}"


def _append_historial(
    db: AsyncSession,
    *,
    incapacidad_id: uuid.UUID,
    anterior: IncapacidadEstado | None,
    nuevo: IncapacidadEstado,
    user_id: uuid.UUID,
    observacion: str | None = None,
) -> None:
    db.add(
        HistorialEstado(
            incapacidad_id=incapacidad_id,
            estado_anterior=anterior,
            estado_nuevo=nuevo,
            user_id=user_id,
            observacion=observacion,
        )
    )


async def _marcar_fallo_extraccion(
    db: AsyncSession,
    incap: Incapacidad,
    actor_user_id: uuid.UUID,
    mensaje: str,
) -> None:
    prev = incap.estado
    incap.estado = IncapacidadEstado.DOC_INCOMPLETA
    detalle = mensaje.strip()
    if len(detalle) > 400:
        detalle = f"{detalle[:397]}..."
    incap.documentacion_faltante = [f"extraccion_ia:{detalle}"]
    obs = mensaje if len(mensaje) <= 2000 else f"{mensaje[:1997]}..."
    _append_historial(
        db,
        incapacidad_id=incap.id,
        anterior=prev,
        nuevo=IncapacidadEstado.DOC_INCOMPLETA,
        user_id=actor_user_id,
        observacion=obs,
    )


async def _obtener_texto_ocr_archivo(path: Path) -> str | None:
    """Ejecuta OCR local; devuelve None si no hay texto o falla sin bloquear el job."""
    try:
        def _run_ocr() -> str:
            resultado = procesar_documento(
                path.read_bytes(),
                nombre_archivo=path.name,
            )
            return resultado.texto.strip()

        texto = await asyncio.to_thread(_run_ocr)
        if texto:
            logger.info(
                "OCR previo a Gemini: %s caracteres (%s)",
                len(texto),
                path.name,
            )
            return texto
    except (OcrProcessorError, OSError, ValueError) as exc:
        logger.warning("OCR omitido antes de Gemini (%s): %s", path.name, exc)
    return None


async def _marcar_exito_extraccion(
    db: AsyncSession,
    incap: Incapacidad,
    actor_user_id: uuid.UUID,
    result: dict[str, object | None],
    raw_response: str,
) -> None:
    existing = await db.scalar(
        select(ExtraccionIA.id).where(ExtraccionIA.incapacidad_id == incap.id)
    )
    if existing is not None:
        logger.warning(
            "Extracción IA omitida: ya existe registro para incapacidad_id=%s",
            incap.id,
        )
        return

    datos, validaciones = _split_extraccion_payload(result)
    datos = enrich_datos_extraidos_for_ui(datos)
    prev = incap.estado
    incap.estado = IncapacidadEstado.EN_VERIFICACION
    db.add(
        ExtraccionIA(
            incapacidad_id=incap.id,
            datos_extraidos=datos,
            validaciones=validaciones,
            raw_response=_truncate_raw_for_db(raw_response),
            api_usada="google_generative_language",
            modelo="gemini-2.5-flash",
        )
    )
    _append_historial(
        db,
        incapacidad_id=incap.id,
        anterior=prev,
        nuevo=IncapacidadEstado.EN_VERIFICACION,
        user_id=actor_user_id,
        observacion="Extracción IA completada.",
    )


async def run_incapacidad_extraction_job(
    incapacidad_id: uuid.UUID,
    archivo_path: str,
    actor_user_id: uuid.UUID,
    *,
    settings: Settings | None = None,
) -> None:
    """
    Ejecuta extracción con Gemini y actualiza incapacidad + extraccion_ia.

    Usa una sesión de BD propia: no comparte la del request HTTP.
    """
    cfg = settings or get_settings()
    async with AsyncSessionLocal() as db:
        try:
            incap = await db.get(Incapacidad, incapacidad_id)
            if incap is None:
                logger.error(
                    "Incapacidad %s no existe; abortando extracción.", incapacidad_id
                )
                return
            if incap.estado != IncapacidadEstado.PROCESANDO_IA:
                logger.info(
                    "Incapacidad %s en estado %s; no se ejecuta extracción.",
                    incapacidad_id,
                    incap.estado,
                )
                return
            path = Path(archivo_path)
            if not path.is_file():
                await _marcar_fallo_extraccion(
                    db,
                    incap,
                    actor_user_id,
                    f"Archivo no disponible en ruta: {archivo_path}",
                )
                await db.commit()
                return

            texto_ocr = await _obtener_texto_ocr_archivo(path)
            try:
                outcome = await extract_from_local_file(
                    path,
                    settings=cfg,
                    texto_ocr=texto_ocr,
                )
            except (GeminiExtractionError, ValueError, FileNotFoundError) as exc:
                await _marcar_fallo_extraccion(
                    db, incap, actor_user_id, _failure_message(exc)
                )
                await db.commit()
                return

            await _marcar_exito_extraccion(
                db,
                incap,
                actor_user_id,
                outcome.normalized,
                outcome.raw_response,
            )
            await db.commit()
        except Exception:
            await db.rollback()
            logger.exception(
                "Fallo no controlado en extracción IA (incapacidad_id=%s)",
                incapacidad_id,
            )
            try:
                async with AsyncSessionLocal() as db2:
                    incap2 = await db2.get(Incapacidad, incapacidad_id)
                    if (
                        incap2 is not None
                        and incap2.estado == IncapacidadEstado.PROCESANDO_IA
                    ):
                        await _marcar_fallo_extraccion(
                            db2,
                            incap2,
                            actor_user_id,
                            "Error interno al procesar la extracción.",
                        )
                        await db2.commit()
            except Exception:
                logger.exception(
                    "No se pudo persistir el fallo de extracción (incapacidad_id=%s)",
                    incapacidad_id,
                )
