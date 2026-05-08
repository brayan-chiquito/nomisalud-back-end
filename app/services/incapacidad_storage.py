"""Persistencia de adjuntos de incapacidades en disco."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.models.incapacidad import ArchivoTipo


class IncapacidadStorageError(Exception):
    """Error de validación o escritura al guardar el adjunto."""


def infer_archivo_tipo(filename: str, content_type: str | None) -> ArchivoTipo:
    """
    Determina el tipo permitido a partir de la extensión y, si viene, el Content-Type.
    """
    suffix = Path(filename).suffix.lower().lstrip(".")
    if suffix == "jpeg":
        suffix = "jpg"
    if suffix not in ("pdf", "jpg", "png"):
        raise IncapacidadStorageError(
            "Tipo de archivo no permitido. Use PDF, JPG/JPEG o PNG."
        )
    tipo = ArchivoTipo(suffix)

    if content_type:
        expected = {
            ArchivoTipo.PDF: {"application/pdf"},
            ArchivoTipo.JPG: {"image/jpeg", "image/jpg"},
            ArchivoTipo.PNG: {"image/png"},
        }[tipo]
        if content_type not in expected:
            raise IncapacidadStorageError(
                "El Content-Type no coincide con la extensión del archivo."
            )

    return tipo


async def persist_incapacidad_attachment(
    upload: UploadFile,
    *,
    base_dir: Path,
    max_bytes: int,
) -> tuple[Path, uuid.UUID, ArchivoTipo, int]:
    """
    Lee el flujo del archivo (con límite de tamaño), lo escribe en disco con nombre
    seguro (UUID + extensión) y devuelve ruta absoluta, UUID de archivo, tipo y bytes.
    """
    tipo = infer_archivo_tipo(upload.filename or "", upload.content_type)
    file_uuid = uuid.uuid4()
    ext = tipo.value
    try:
        base_resolved = base_dir.resolve()
    except OSError as exc:
        raise IncapacidadStorageError("Directorio de almacenamiento inválido.") from exc

    base_dir.mkdir(parents=True, exist_ok=True)
    dest = (base_dir / f"{file_uuid}.{ext}").resolve()
    try:
        dest.relative_to(base_resolved)
    except ValueError as exc:
        msg = "Ruta de destino fuera del directorio permitido."
        raise IncapacidadStorageError(msg) from exc

    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await upload.read(1024 * 64)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise IncapacidadStorageError(
                f"El archivo supera el tamaño máximo permitido ({max_bytes} bytes)."
            )
        chunks.append(chunk)

    data = b"".join(chunks)
    if not data:
        raise IncapacidadStorageError("El archivo está vacío.")

    def _write() -> None:
        dest.write_bytes(data)

    await asyncio.to_thread(_write)
    return dest, file_uuid, tipo, len(data)
