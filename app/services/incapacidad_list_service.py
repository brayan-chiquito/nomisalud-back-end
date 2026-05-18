"""Consulta paginada de incapacidades con filtros (SCRUM-130)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import ceil

from sqlalchemy import and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.extraccion_ia import ExtraccionIA
from app.models.incapacidad import ArchivoTipo, Incapacidad, IncapacidadEstado
from app.models.user import User


def total_pages(total: int, page_size: int) -> int:
    """Número de páginas; 0 si no hay registros."""
    if total <= 0 or page_size <= 0:
        return 0
    return ceil(total / page_size)


def _tipo_es_archivo(tipo: str) -> ArchivoTipo | None:
    try:
        return ArchivoTipo(tipo.strip().lower())
    except ValueError:
        return None


@dataclass(frozen=True)
class IncapacidadListRow:
    """Fila de listado: trámite + datos de colaborador y extracción IA."""

    incapacidad: Incapacidad
    colaborador_nombre: str | None
    colaborador_email: str | None
    entidad_nombre: str | None
    entidad_tipo: str | None
    entidad_nit: str | None
    entidad_ciudad: str | None
    incapacidad_tipo_extraido: str | None


async def list_incapacidades_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    estado: IncapacidadEstado | None,
    tipo: str | None,
    entidad: str | None,
    colaborador_id_scope: uuid.UUID | None,
) -> tuple[list[IncapacidadListRow], int]:
    """
    Lista incapacidades con filtros opcionales y paginación.

    Incluye siempre datos del colaborador (``users``) y, si existe, de
    ``extraccion_ia.datos_extraidos`` (entidad e incapacidad.tipo del JSON).

    - ``tipo``: si coincide con pdf/jpg/png filtra ``archivo_tipo``; si no, filtra
      ``datos_extraidos.incapacidad.tipo`` (solo filas con extracción IA).
    - ``entidad``: subcadena insensible a mayúsculas en
      ``datos_extraidos.entidad.nombre``.
    """
    Colaborador = aliased(User)
    conds = []
    if colaborador_id_scope is not None:
        conds.append(Incapacidad.colaborador_id == colaborador_id_scope)
    if estado is not None:
        conds.append(Incapacidad.estado == estado)

    tipo_norm = tipo.strip() if tipo and tipo.strip() else None
    entidad_norm = entidad.strip() if entidad and entidad.strip() else None

    archivo_tipo: ArchivoTipo | None = None
    tipo_json: str | None = None
    if tipo_norm:
        archivo_tipo = _tipo_es_archivo(tipo_norm)
        if archivo_tipo is None:
            tipo_json = tipo_norm
        else:
            conds.append(Incapacidad.archivo_tipo == archivo_tipo)

    nombre_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "nombre"
    )
    tipo_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "incapacidad", "tipo"
    )
    if entidad_norm:
        conds.append(nombre_path.ilike(f"%{entidad_norm}%"))
    if tipo_json is not None:
        conds.append(tipo_path == tipo_json)

    entidad_tipo_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "tipo"
    )
    entidad_nit_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "nit"
    )
    entidad_ciudad_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "ciudad"
    )

    where_clause = and_(*conds) if conds else true()

    count_stmt = (
        select(func.count(Incapacidad.id))
        .select_from(Incapacidad)
        .outerjoin(Colaborador, Colaborador.id == Incapacidad.colaborador_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(where_clause)
    )
    total = int((await db.execute(count_stmt)).scalar_one())

    offset = (page - 1) * page_size
    list_stmt = (
        select(
            Incapacidad,
            Colaborador.nombre_completo,
            Colaborador.email,
            nombre_path,
            entidad_tipo_path,
            entidad_nit_path,
            entidad_ciudad_path,
            tipo_path,
        )
        .select_from(Incapacidad)
        .outerjoin(Colaborador, Colaborador.id == Incapacidad.colaborador_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(where_clause)
        .order_by(Incapacidad.fecha_recepcion.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(list_stmt)
    out: list[IncapacidadListRow] = []
    for row in result.all():
        inc, nom, eml, en, et, nit, ec, tipo_ext = row
        out.append(
            IncapacidadListRow(
                incapacidad=inc,
                colaborador_nombre=nom,
                colaborador_email=eml,
                entidad_nombre=en,
                entidad_tipo=et,
                entidad_nit=nit,
                entidad_ciudad=ec,
                incapacidad_tipo_extraido=tipo_ext,
            )
        )
    return out, total


async def list_mis_incapacidades_paginated(
    db: AsyncSession,
    *,
    colaborador_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[Incapacidad], int]:
    """
    Lista trámites del colaborador autenticado (filtro estricto por titular).

    Ordenados por ``updated_at`` descendente (última modificación primero).
    """
    where = Incapacidad.colaborador_id == colaborador_id

    count_stmt = select(func.count(Incapacidad.id)).where(where)
    total = int((await db.execute(count_stmt)).scalar_one())

    offset = (page - 1) * page_size
    list_stmt = (
        select(Incapacidad)
        .where(where)
        .order_by(Incapacidad.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(list_stmt)
    return list(result.scalars().all()), total
