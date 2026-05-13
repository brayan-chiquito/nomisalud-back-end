"""
Campos de `datos_extraidos` alineados con el contrato UI del front.

La IA persiste el esquema del prompt (`paciente`, `incapacidad.total_dias`,
`diagnostico` anidado). El dashboard espera `colaborador` y campos planos en
`incapacidad` (`dias`, `origen`, `diagnostico_principal`, `codigo_cie10`,
`diagnostico`). Esta capa fusiona ambos sin borrar el JSON original.
"""

from __future__ import annotations

import copy
from typing import Any


def _as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        return s or None
    return str(value).strip() or None


def _origen_desde_tipo_incapacidad(tipo: str | None) -> str | None:
    if not tipo:
        return None
    key = tipo.strip().lower().replace(" ", "_").replace("-", "_")
    mapa = {
        "enfermedad_general": "Enfermedad general",
        "accidente_trabajo": "Accidente de trabajo",
        "accidente_transito": "Accidente de tránsito",
        "enfermedad_laboral": "Enfermedad laboral",
        "maternidad": "Maternidad",
        "paternidad": "Paternidad",
    }
    return mapa.get(key, tipo.replace("_", " ").title())


def enrich_datos_extraidos_for_ui(data: dict[str, Any] | None) -> dict[str, Any]:
    """
    Devuelve una copia de ``data`` con ``colaborador`` y campos planos en
    ``incapacidad`` rellenados desde ``paciente`` y ``diagnostico`` cuando aplica.

    Idempotente: puede invocarse varias veces sobre el mismo dict.
    """
    if not data:
        return {}
    out: dict[str, Any] = copy.deepcopy(data)

    paciente = out.get("paciente") if isinstance(out.get("paciente"), dict) else {}
    incap = out.get("incapacidad") if isinstance(out.get("incapacidad"), dict) else {}
    diag = out.get("diagnostico") if isinstance(out.get("diagnostico"), dict) else {}

    # --- colaborador (alias UI de paciente + overrides si ya vienen del front)
    col_in = out.get("colaborador") if isinstance(out.get("colaborador"), dict) else {}
    nombre = _as_str(col_in.get("nombre_completo")) or _as_str(
        paciente.get("nombre_completo")
    )
    documento = _as_str(col_in.get("documento")) or _as_str(
        paciente.get("numero_documento")
    )
    if nombre is not None or documento is not None:
        out["colaborador"] = {
            "nombre_completo": nombre,
            "documento": documento,
        }

    # --- diagnóstico plano (evita que el front reciba solo el objeto anidado)
    codigo = (
        _as_str(diag.get("codigo_cie10"))
        or _as_str(incap.get("codigo_cie10"))
    )
    descripcion = (
        _as_str(diag.get("descripcion"))
        or _as_str(incap.get("diagnostico"))
    )

    principal: str | None = None
    if codigo and descripcion and codigo != descripcion:
        principal = f"{codigo} - {descripcion}"
    elif codigo:
        principal = codigo
    elif descripcion:
        principal = descripcion

    incap_merged = dict(incap)

    total_dias = incap.get("total_dias")
    dias_str: str | None = None
    if total_dias is not None:
        if isinstance(total_dias, bool):
            pass
        elif isinstance(total_dias, int | float):
            dias_str = str(int(total_dias))
        else:
            dias_str = _as_str(total_dias)
    if dias_str is None:
        dias_str = _as_str(incap.get("dias"))

    tipo = _as_str(incap.get("tipo"))
    if tipo:
        origen = _origen_desde_tipo_incapacidad(tipo)
    else:
        origen = _as_str(incap.get("origen"))

    if dias_str is not None:
        incap_merged["dias"] = dias_str
    if origen is not None:
        incap_merged["origen"] = origen
    if codigo is not None:
        incap_merged["codigo_cie10"] = codigo
    if descripcion is not None:
        incap_merged["diagnostico"] = descripcion
    if principal is not None:
        incap_merged["diagnostico_principal"] = principal

    out["incapacidad"] = incap_merged
    return out
