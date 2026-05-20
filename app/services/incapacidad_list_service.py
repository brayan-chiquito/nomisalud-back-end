"""Consulta paginada de incapacidades con filtros (SCRUM-130)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from math import ceil

from sqlalchemy import Select, and_, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.extraccion_ia import ExtraccionIA
from app.models.incapacidad import ArchivoTipo, Incapacidad, IncapacidadEstado
from app.models.user import User
from app.services.urgencia_service import cargar_indice_plazos, urgencia_desde_indice


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
    """Fila de listado: trámite + datos de colaborador, extracción IA y urgencia."""

    incapacidad: Incapacidad
    colaborador_nombre: str | None
    colaborador_email: str | None
    entidad_nombre: str | None
    entidad_tipo: str | None
    entidad_nit: str | None
    entidad_ciudad: str | None
    incapacidad_tipo_extraido: str | None
    urgencia: str


def _build_list_row(
    inc: Incapacidad,
    nom: str | None,
    eml: str | None,
    en: str | None,
    et: str | None,
    nit: str | None,
    ec: str | None,
    tipo_ext: str | None,
    *,
    indice_plazos: dict,
) -> IncapacidadListRow:
    return IncapacidadListRow(
        incapacidad=inc,
        colaborador_nombre=nom,
        colaborador_email=eml,
        entidad_nombre=en,
        entidad_tipo=et,
        entidad_nit=nit,
        entidad_ciudad=ec,
        incapacidad_tipo_extraido=tipo_ext,
        urgencia=urgencia_desde_indice(
            indice_plazos,
            fecha_recepcion=inc.fecha_recepcion,
            entidad_nombre=en,
            tipo_incapacidad=tipo_ext,
        ),
    )


def _list_select_and_where(
    *,
    estado: IncapacidadEstado | None,
    tipo: str | None,
    entidad: str | None,
    colaborador_id_scope: uuid.UUID | None,
) -> tuple[aliased, aliased, object, object, object, object, object, object, object]:
    """Arma joins y cláusula WHERE compartida por conteo y listado."""
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
    return (
        Colaborador,
        nombre_path,
        tipo_path,
        entidad_tipo_path,
        entidad_nit_path,
        entidad_ciudad_path,
        where_clause,
        archivo_tipo,
        tipo_json,
    )


def _list_stmt(
    Colaborador: aliased,
    nombre_path: object,
    tipo_path: object,
    entidad_tipo_path: object,
    entidad_nit_path: object,
    entidad_ciudad_path: object,
    where_clause: object,
) -> Select:
    return (
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
    )


async def list_incapacidades_paginated(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    estado: IncapacidadEstado | None,
    tipo: str | None,
    entidad: str | None,
    colaborador_id_scope: uuid.UUID | None,
    urgencia_filtro: str | None = None,
) -> tuple[list[IncapacidadListRow], int]:
    """
    Lista incapacidades con filtros opcionales y paginación.

    Incluye siempre datos del colaborador (``users``) y, si existe, de
    ``extraccion_ia.datos_extraidos`` (entidad e incapacidad.tipo del JSON).

    - ``tipo``: si coincide con pdf/jpg/png filtra ``archivo_tipo``; si no, filtra
      ``datos_extraidos.incapacidad.tipo`` (solo filas con extracción IA).
    - ``entidad``: subcadena insensible a mayúsculas en
      ``datos_extraidos.entidad.nombre``.
    - ``urgencia_filtro``: si se indica, carga todos los candidatos, calcula
      urgencia y pagina en memoria (``verde`` | ``amarillo`` | ``rojo``).
    """
    (
        Colaborador,
        nombre_path,
        tipo_path,
        entidad_tipo_path,
        entidad_nit_path,
        entidad_ciudad_path,
        where_clause,
        _archivo_tipo,
        _tipo_json,
    ) = _list_select_and_where(
        estado=estado,
        tipo=tipo,
        entidad=entidad,
        colaborador_id_scope=colaborador_id_scope,
    )

    indice_plazos = await cargar_indice_plazos(db)

    if urgencia_filtro is not None:
        list_stmt = _list_stmt(
            Colaborador,
            nombre_path,
            tipo_path,
            entidad_tipo_path,
            entidad_nit_path,
            entidad_ciudad_path,
            where_clause,
        )
        result = await db.execute(list_stmt)
        filtradas: list[IncapacidadListRow] = []
        for row in result.all():
            inc, nom, eml, en, et, nit, ec, tipo_ext = row
            item = _build_list_row(
                inc, nom, eml, en, et, nit, ec, tipo_ext, indice_plazos=indice_plazos
            )
            if item.urgencia == urgencia_filtro:
                filtradas.append(item)
        total = len(filtradas)
        offset = (page - 1) * page_size
        return filtradas[offset : offset + page_size], total

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
        _list_stmt(
            Colaborador,
            nombre_path,
            tipo_path,
            entidad_tipo_path,
            entidad_nit_path,
            entidad_ciudad_path,
            where_clause,
        )
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(list_stmt)
    out: list[IncapacidadListRow] = []
    for row in result.all():
        inc, nom, eml, en, et, nit, ec, tipo_ext = row
        out.append(
            _build_list_row(
                inc, nom, eml, en, et, nit, ec, tipo_ext, indice_plazos=indice_plazos
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
