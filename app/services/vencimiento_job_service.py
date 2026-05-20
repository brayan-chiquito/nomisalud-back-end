"""Revisión diaria de trámites próximos a vencer (SCRUM-180 / 181 / 182)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings, get_settings
from app.models.alerta_enviada import TipoAlerta
from app.models.extraccion_ia import ExtraccionIA
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import User
from app.services.alerta_enviada_service import (
    existe_alerta_reciente,
    registrar_alerta_enviada,
)
from app.services.mail_service import (
    AlertaVencimientoCorreo,
    enviar_alerta_vencimiento,
    mail_configurado,
)
from app.services.urgencia_service import (
    NivelUrgencia,
    calcular_dias_restantes,
    cargar_indice_plazos,
    resolver_plazo_en_indice,
    urgencia_desde_indice,
)

logger = logging.getLogger(__name__)

ESTADOS_REVISABLES = (
    IncapacidadEstado.EN_VERIFICACION,
    IncapacidadEstado.INCONSISTENCIA_DETECTADA,
    IncapacidadEstado.DOC_INCOMPLETA,
)

_URGENCIA_A_TIPO_ALERTA: dict[str, TipoAlerta] = {
    NivelUrgencia.AMARILLO.value: TipoAlerta.VENCIMIENTO_AMARILLO,
    NivelUrgencia.ROJO.value: TipoAlerta.VENCIMIENTO_ROJO,
}


@dataclass
class VencimientoJobResultado:
    """Resumen auditable de una ejecución del job."""

    evaluados: int = 0
    alertas_enviadas: int = 0
    omitidos_duplicado: int = 0
    omitidos_verde: int = 0
    errores: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _CandidatoAlerta:
    incapacidad_id: uuid.UUID
    radicado: str
    colaborador_nombre: str
    entidad_nombre: str
    tipo_incapacidad: str
    dias_restantes: int
    nivel_urgencia: str
    tipo_alerta: TipoAlerta


def _stmt_incapacidades_revisables() -> Select:
    colab_user = aliased(User)
    nombre_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "entidad", "nombre"
    )
    tipo_path = func.jsonb_extract_path_text(
        ExtraccionIA.datos_extraidos, "incapacidad", "tipo"
    )
    return (
        select(
            Incapacidad,
            colab_user.nombre_completo,
            nombre_path,
            tipo_path,
        )
        .select_from(Incapacidad)
        .join(colab_user, colab_user.id == Incapacidad.colaborador_id)
        .outerjoin(ExtraccionIA, ExtraccionIA.incapacidad_id == Incapacidad.id)
        .where(Incapacidad.estado.in_(ESTADOS_REVISABLES))
    )


async def _fetch_filas_revisables(db: AsyncSession) -> list:
    stmt = _stmt_incapacidades_revisables()
    return (await db.execute(stmt)).all()


def _construir_candidato(
    inc: Incapacidad,
    colaborador_nombre: str | None,
    entidad_nombre: str | None,
    tipo_incapacidad: str | None,
    *,
    urgencia: str,
    tipo_alerta: TipoAlerta,
    indice_plazos: dict,
    ref: datetime,
) -> _CandidatoAlerta:
    plazo = resolver_plazo_en_indice(
        indice_plazos,
        entidad_nombre=entidad_nombre,
        tipo_incapacidad=tipo_incapacidad,
    )
    dias_restantes = 0
    if plazo is not None:
        dias_restantes = calcular_dias_restantes(
            fecha_recepcion=inc.fecha_recepcion,
            dias_limite=plazo.dias_limite,
            fecha_evaluacion=ref,
        )
    return _CandidatoAlerta(
        incapacidad_id=inc.id,
        radicado=inc.radicado,
        colaborador_nombre=colaborador_nombre or "Sin nombre",
        entidad_nombre=entidad_nombre or "Sin entidad",
        tipo_incapacidad=tipo_incapacidad or "general",
        dias_restantes=dias_restantes,
        nivel_urgencia=urgencia,
        tipo_alerta=tipo_alerta,
    )


def _extraer_candidatos(
    rows: list,
    indice_plazos: dict,
    ref: datetime,
) -> tuple[list[_CandidatoAlerta], int, int]:
    candidatos: list[_CandidatoAlerta] = []
    evaluados = 0
    omitidos_verde = 0
    for inc, nom, entidad_nombre, tipo_incapacidad in rows:
        evaluados += 1
        urgencia = urgencia_desde_indice(
            indice_plazos,
            fecha_recepcion=inc.fecha_recepcion,
            entidad_nombre=entidad_nombre,
            tipo_incapacidad=tipo_incapacidad,
            fecha_evaluacion=ref,
        )
        if urgencia == NivelUrgencia.VERDE.value:
            omitidos_verde += 1
            continue
        tipo_alerta = _URGENCIA_A_TIPO_ALERTA.get(urgencia)
        if tipo_alerta is None:
            continue
        candidatos.append(
            _construir_candidato(
                inc,
                nom,
                entidad_nombre,
                tipo_incapacidad,
                urgencia=urgencia,
                tipo_alerta=tipo_alerta,
                indice_plazos=indice_plazos,
                ref=ref,
            )
        )
    return candidatos, evaluados, omitidos_verde


async def _procesar_envios(
    db: AsyncSession,
    candidatos: list[_CandidatoAlerta],
    settings: Settings,
    ref: datetime,
    ventana_dias: int,
) -> tuple[int, int, list[str]]:
    enviadas = 0
    duplicados = 0
    errores: list[str] = []
    for cand in candidatos:
        if await existe_alerta_reciente(
            db,
            incapacidad_id=cand.incapacidad_id,
            tipo_alerta=cand.tipo_alerta,
            ventana_dias=ventana_dias,
            fecha_referencia=ref,
        ):
            duplicados += 1
            logger.debug(
                "Alerta omitida (duplicado) radicado=%s tipo=%s",
                cand.radicado,
                cand.tipo_alerta.value,
            )
            continue
        try:
            await enviar_alerta_vencimiento(
                AlertaVencimientoCorreo(
                    radicado=cand.radicado,
                    colaborador_nombre=cand.colaborador_nombre,
                    entidad_nombre=cand.entidad_nombre,
                    tipo_incapacidad=cand.tipo_incapacidad,
                    dias_restantes=cand.dias_restantes,
                    nivel_urgencia=cand.nivel_urgencia,
                ),
                settings=settings,
            )
            await registrar_alerta_enviada(
                db,
                incapacidad_id=cand.incapacidad_id,
                tipo_alerta=cand.tipo_alerta,
                enviada_en=ref,
            )
            enviadas += 1
        except Exception as exc:
            msg = f"radicado={cand.radicado}: {exc}"
            logger.exception("Error enviando alerta de vencimiento: %s", msg)
            errores.append(msg)
    return enviadas, duplicados, errores


async def revisar_vencimientos_y_alertar(
    db: AsyncSession,
    *,
    fecha_evaluacion: datetime | None = None,
) -> VencimientoJobResultado:
    """
    Busca trámites en ventana amarilla/roja, evita duplicados (7 días)
    y envía correos de alerta.
    """
    settings = get_settings()
    ref = fecha_evaluacion or datetime.now(UTC)

    if not mail_configurado(settings):
        logger.warning(
            "Job de vencimientos: correo deshabilitado o sin SMTP/destinatarios; "
            "no se enviarán alertas."
        )
        return VencimientoJobResultado()

    indice_plazos = await cargar_indice_plazos(db)
    rows = await _fetch_filas_revisables(db)
    candidatos, evaluados, omitidos_verde = _extraer_candidatos(
        rows, indice_plazos, ref
    )
    enviadas, duplicados, errores = await _procesar_envios(
        db,
        candidatos,
        settings,
        ref,
        settings.ALERTAS_DEDUP_DIAS,
    )
    await db.commit()
    return VencimientoJobResultado(
        evaluados=evaluados,
        alertas_enviadas=enviadas,
        omitidos_duplicado=duplicados,
        omitidos_verde=omitidos_verde,
        errores=errores,
    )
