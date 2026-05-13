"""Consulta de detalle de incapacidad con extracción IA (SCRUM-133)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.extraccion_ia import ExtraccionIA
from app.models.incapacidad import Incapacidad
from app.models.user import User


@dataclass(frozen=True)
class IncapacidadDetalleBundle:
    """Trámite con colaborador y extracción IA opcional."""

    incapacidad: Incapacidad
    extraccion_ia: ExtraccionIA | None
    colaborador_nombre: str | None
    colaborador_email: str | None


async def get_incapacidad_detalle(
    db: AsyncSession,
    incapacidad_id: uuid.UUID,
) -> IncapacidadDetalleBundle | None:
    """
    Obtiene incapacidad por id con LEFT JOIN a extraccion_ia y datos del colaborador.
    """
    Colaborador = aliased(User)
    stmt = (
        select(
            Incapacidad,
            ExtraccionIA,
            Colaborador.nombre_completo,
            Colaborador.email,
        )
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .outerjoin(Colaborador, Colaborador.id == Incapacidad.colaborador_id)
        .where(Incapacidad.id == incapacidad_id)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    inc, ext, nom, eml = row
    return IncapacidadDetalleBundle(
        incapacidad=inc,
        extraccion_ia=ext,
        colaborador_nombre=nom,
        colaborador_email=eml,
    )


def resolve_archivo_under_storage(
    archivo_path: str | None,
    storage_dir: Path,
) -> Path | None:
    """
    Devuelve la ruta resuelta del adjunto solo si queda bajo ``storage_dir``.
    """
    if not archivo_path or not archivo_path.strip():
        return None
    try:
        base = storage_dir.resolve()
        candidate = Path(archivo_path).resolve()
        candidate.relative_to(base)
    except (OSError, ValueError):
        return None
    if not candidate.is_file():
        return None
    return candidate
