"""Inconsistencias en prompt y extracción (SCRUM-169 / SCRUM-170)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.inconsistencia import Inconsistencia
from app.services.ai_extractor import (
    InconsistenciaExtraida,
    LocalExtractionResult,
    load_extraction_prompt,
    parse_inconsistencias_desde_extraccion,
)
from app.services.incapacidad_extraction_jobs import run_incapacidad_extraction_job


def test_prompt_incluye_campo_inconsistencias_y_categorias():
    prompt = load_extraction_prompt()
    assert '"inconsistencias"' in prompt
    assert "INCONSISTENCIAS ESTRUCTURADAS" in prompt
    for categoria in (
        '"fechas"',
        '"dias"',
        '"genero_tipo"',
        '"identificacion"',
        '"legibilidad"',
        '"dato_faltante"',
    ):
        assert categoria in prompt


def test_parse_inconsistencias_tres_tipos_distintos():
    payload = {
        "inconsistencias": [
            {
                "tipo": "fechas",
                "descripcion": "fecha_fin anterior a fecha_inicio",
            },
            {
                "tipo": "dias",
                "descripcion": "total_dias 10 no coincide con rango 8",
            },
            {
                "tipo": "identificacion",
                "descripcion": "numero_documento con letras",
            },
            {"tipo": "invalido", "descripcion": "ignorado"},
            {"tipo": "fechas", "descripcion": ""},
        ]
    }
    out = parse_inconsistencias_desde_extraccion(payload)
    assert len(out) == 3
    tipos = {item.tipo for item in out}
    assert tipos == {"fechas", "dias", "identificacion"}


def test_parse_inconsistencias_vacio_si_ausente():
    assert parse_inconsistencias_desde_extraccion({}) == ()
    assert parse_inconsistencias_desde_extraccion({"inconsistencias": None}) == ()


@pytest.mark.asyncio
async def test_job_con_inconsistencias_estado_y_persistencia(monkeypatch):
    from tests.services.test_incapacidad_extraction_jobs import _fake_session_cm

    incap_id = uuid.uuid4()
    user_id = uuid.uuid4()
    incap = MagicMock(spec=Incapacidad)
    incap.id = incap_id
    incap.estado = IncapacidadEstado.PROCESANDO_IA

    inconsistencias = (
        InconsistenciaExtraida(tipo="fechas", descripcion="fin <= inicio"),
        InconsistenciaExtraida(tipo="dias", descripcion="dias no cuadran"),
    )
    outcome = LocalExtractionResult(
        normalized={
            "paciente": None,
            "incapacidad": None,
            "diagnostico": None,
            "entidad": None,
            "medico": None,
            "documento": None,
            "validaciones": {"fechas_ok": False},
        },
        raw_response=json.dumps({"validaciones": {"fechas_ok": False}}),
        inconsistencias=inconsistencias,
    )

    session = AsyncMock()
    session.get = AsyncMock(return_value=incap)
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.AsyncSessionLocal",
        lambda: _fake_session_cm(session),
    )
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs._obtener_texto_ocr_archivo",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.extract_from_local_file",
        AsyncMock(return_value=outcome),
    )

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"

    await run_incapacidad_extraction_job(
        incap_id,
        "/tmp/doc.pdf",
        user_id,
        settings=settings,
    )

    assert incap.estado == IncapacidadEstado.INCONSISTENCIA_DETECTADA
    added = [c.args[0] for c in session.add.call_args_list if c.args]
    inconsistencias_db = [o for o in added if isinstance(o, Inconsistencia)]
    assert len(inconsistencias_db) == 2
    assert {i.tipo for i in inconsistencias_db} == {"fechas", "dias"}
