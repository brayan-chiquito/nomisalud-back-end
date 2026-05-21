"""Utilidades de rango temporal para conciliación (mes/año)."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class RangoPeriodo:
    """Intervalo [inicio, fin] inclusive en UTC para un mes calendario."""

    mes: int
    anio: int
    inicio: datetime
    fin: datetime


def rango_periodo_mes_anio(*, mes: int, anio: int) -> RangoPeriodo:
    if not 1 <= mes <= 12:
        raise ValueError("mes debe estar entre 1 y 12.")
    if anio < 2000 or anio > 2100:
        raise ValueError("anio fuera de rango permitido.")
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    inicio = datetime(anio, mes, 1, 0, 0, 0, tzinfo=UTC)
    fin = datetime(anio, mes, ultimo_dia, 23, 59, 59, tzinfo=UTC)
    return RangoPeriodo(mes=mes, anio=anio, inicio=inicio, fin=fin)
