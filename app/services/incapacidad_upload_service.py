"""Registro de incapacidad tras carga multipart: disco + transacción BD."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.repositories.user_repository import get_user_by_id
from app.services.incapacidad_storage import persist_incapacidad_attachment


def _new_radicado_candidate() -> str:
    """Genera un radicado único candidato (máx. 20 caracteres, alfanumérico)."""
    return f"IN{uuid.uuid4().hex[:18].upper()}"


async def _unlink_quiet(path: Path) -> None:
    def _unlink() -> None:
        path.unlink(missing_ok=True)

    await asyncio.to_thread(_unlink)


async def register_incapacidad_upload(
    db: AsyncSession,
    *,
    upload: UploadFile,
    colaborador_id: uuid.UUID,
    cargado_por_id: uuid.UUID,
    storage_dir: Path,
    max_upload_bytes: int,
) -> Incapacidad:
    """
    Valida colaborador, persiste el archivo en disco e inserta la fila en
    `incapacidades` con estado inicial `recibida`. El commit lo realiza `get_db`.

    Usa savepoints para reintentar colisiones de `radicado` sin cerrar la transacción.
    """
    colaborador = await get_user_by_id(db, colaborador_id)
    if colaborador is None:
        raise ValueError("El colaborador indicado no existe.")

    stored_path, file_uuid, archivo_tipo, tamano = await persist_incapacidad_attachment(
        upload,
        base_dir=storage_dir,
        max_bytes=max_upload_bytes,
    )

    fecha_recepcion = datetime.now(UTC)
    last_error: IntegrityError | None = None
    row: Incapacidad | None = None

    try:
        for _ in range(5):
            radicado = _new_radicado_candidate()
            candidate = Incapacidad(
                radicado=radicado,
                colaborador_id=colaborador_id,
                cargado_por=cargado_por_id,
                user_id=colaborador_id,
                archivo_uuid=str(file_uuid),
                archivo_path=str(stored_path),
                archivo_tipo=archivo_tipo,
                archivo_tamano_bytes=tamano,
                estado=IncapacidadEstado.RECIBIDA,
                documentacion_faltante=None,
                fecha_recepcion=fecha_recepcion,
            )
            try:
                async with db.begin_nested():
                    db.add(candidate)
                    await db.flush()
            except IntegrityError as exc:
                last_error = exc
                if _is_unique_radicado_violation(exc):
                    continue
                raise
            row = candidate
            break

        if row is None:
            raise RuntimeError("No se pudo generar un radicado único.") from last_error

        await db.refresh(row)
        return row
    except Exception:
        await _unlink_quiet(stored_path)
        raise


def _is_unique_radicado_violation(exc: IntegrityError) -> bool:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    if sqlstate == "23505":
        return True
    pgcode = getattr(orig, "pgcode", None)
    return pgcode == "23505"
