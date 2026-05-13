"""Tests de normalización datos_extraidos para UI."""

from app.services.datos_extraidos_ui import enrich_datos_extraidos_for_ui


def test_enrich_vacio():
    assert enrich_datos_extraidos_for_ui(None) == {}
    assert enrich_datos_extraidos_for_ui({}) == {}


def test_enrich_desde_esquema_ia_prompt():
    raw = {
        "paciente": {
            "nombre_completo": "USUARIO DE PRUEBA SISTEMA",
            "numero_documento": "1234567890",
        },
        "incapacidad": {
            "tipo": "enfermedad_general",
            "fecha_inicio": "2026-05-09",
            "fecha_fin": "2026-05-11",
            "total_dias": 3,
        },
        "diagnostico": {
            "codigo_cie10": "K30X",
            "descripcion": "Dispepsia",
        },
        "entidad": {"nombre": "EPS X", "tipo": "EPS", "nit": "800"},
    }
    out = enrich_datos_extraidos_for_ui(raw)
    assert out["colaborador"]["nombre_completo"] == "USUARIO DE PRUEBA SISTEMA"
    assert out["colaborador"]["documento"] == "1234567890"
    assert out["incapacidad"]["dias"] == "3"
    assert out["incapacidad"]["origen"] == "Enfermedad general"
    assert out["incapacidad"]["codigo_cie10"] == "K30X"
    assert out["incapacidad"]["diagnostico"] == "Dispepsia"
    assert out["incapacidad"]["diagnostico_principal"] == "K30X - Dispepsia"
    assert out["diagnostico"]["codigo_cie10"] == "K30X"


def test_enrich_codigo_sin_descripcion():
    out = enrich_datos_extraidos_for_ui(
        {
            "paciente": {},
            "incapacidad": {"tipo": "maternidad"},
            "diagnostico": {"codigo_cie10": "Z34", "descripcion": None},
            "entidad": {},
        }
    )
    assert out["incapacidad"]["diagnostico_principal"] == "Z34"
    assert out["incapacidad"]["origen"] == "Maternidad"


def test_enrich_respeta_colaborador_explicito():
    out = enrich_datos_extraidos_for_ui(
        {
            "colaborador": {"nombre_completo": "Override", "documento": "99"},
            "paciente": {"nombre_completo": "IA", "numero_documento": "1"},
            "incapacidad": {},
            "diagnostico": {},
            "entidad": {},
        }
    )
    assert out["colaborador"]["nombre_completo"] == "Override"
    assert out["colaborador"]["documento"] == "99"
