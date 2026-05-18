"""Reglas compartidas de estados para verificación y cambio manual (RRHH)."""

from __future__ import annotations

from app.models.incapacidad import IncapacidadEstado

# Origen → destinos permitidos vía PATCH /estado
TRANSICIONES_PATCH_DESDE: dict[IncapacidadEstado, frozenset[IncapacidadEstado]] = {
    IncapacidadEstado.EN_VERIFICACION: frozenset(
        {
            IncapacidadEstado.TRANSCRITA,
            IncapacidadEstado.DOC_INCOMPLETA,
            IncapacidadEstado.RECHAZADA,
        }
    ),
    IncapacidadEstado.DOC_INCOMPLETA: frozenset({IncapacidadEstado.EN_VERIFICACION}),
    IncapacidadEstado.TRANSCRITA: frozenset({IncapacidadEstado.COBRADA}),
    IncapacidadEstado.COBRADA: frozenset({IncapacidadEstado.PAGADA}),
}

# PUT /verificar (revisión de extracción IA)
ESTADOS_QUE_ADMITEN_VERIFICAR: frozenset[IncapacidadEstado] = frozenset(
    {
        IncapacidadEstado.EN_VERIFICACION,
        IncapacidadEstado.DOC_INCOMPLETA,
        IncapacidadEstado.PROCESANDO_IA,
    }
)

ESTADO_TRAS_CONFIRMAR_VERIFICACION = IncapacidadEstado.EN_VERIFICACION
ESTADO_TRAS_RECHAZAR_VERIFICACION = IncapacidadEstado.RECHAZADA


def destinos_patch_validos(desde: IncapacidadEstado) -> frozenset[IncapacidadEstado]:
    return TRANSICIONES_PATCH_DESDE.get(desde, frozenset())
