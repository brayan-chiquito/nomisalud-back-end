"""Tests de la tarea en segundo plano de extracción IA (SCRUM-127)."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.extraccion_ia import ExtraccionIA
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.services.ai_extractor import GeminiExtractionError, LocalExtractionResult
from app.services.incapacidad_extraction_jobs import (
    _split_extraccion_payload,
    _truncate_raw_for_db,
    run_incapacidad_extraction_job,
)


def test_split_extraccion_payload_separa_validaciones():
    raw = {
        "paciente": {"a": 1},
        "incapacidad": None,
        "diagnostico": None,
        "entidad": None,
        "medico": None,
        "documento": None,
        "validaciones": {"fechas_ok": True},
    }
    datos, val = _split_extraccion_payload(raw)
    assert "validaciones" not in datos
    assert datos["paciente"] == {"a": 1}
    assert val == {"fechas_ok": True}


def test_truncate_raw_for_db_limita_tamaño():
    huge = "x" * 600_000
    out = _truncate_raw_for_db(huge)
    assert len(out) < len(huge)
    assert "truncado" in out


def test_split_extraccion_payload_validaciones_no_dict():
    raw = {
        "paciente": None,
        "incapacidad": None,
        "diagnostico": None,
        "entidad": None,
        "medico": None,
        "documento": None,
        "validaciones": "mal",
    }
    datos, val = _split_extraccion_payload(raw)
    assert val is None


def _fake_session_cm(session: AsyncMock):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_job_exito_actualiza_en_verificacion(monkeypatch):
    incap_id = uuid.uuid4()
    actor = uuid.uuid4()

    incap = MagicMock(spec=Incapacidad)
    incap.id = incap_id
    incap.estado = IncapacidadEstado.PROCESANDO_IA

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

    async def fake_extract(*_a, **_k):
        return LocalExtractionResult(
            normalized={
                "paciente": {"nombre_completo": "X"},
                "incapacidad": {"total_dias": 3},
                "diagnostico": None,
                "entidad": None,
                "medico": None,
                "documento": None,
                "validaciones": {"dias_ok": True},
            },
            raw_response='{"paciente":{"nombre_completo":"X"}}',
        )

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.extract_from_local_file",
        fake_extract,
    )

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"

    await run_incapacidad_extraction_job(
        incap_id, "/z/doc.pdf", actor, settings=settings
    )

    assert incap.estado == IncapacidadEstado.EN_VERIFICACION
    session.commit.assert_awaited_once()
    assert session.add.call_count == 2
    added = [c.args[0] for c in session.add.call_args_list if c.args]
    ext_row = next(obj for obj in added if isinstance(obj, ExtraccionIA))
    assert ext_row.raw_response == '{"paciente":{"nombre_completo":"X"}}'


@pytest.mark.asyncio
async def test_job_archivo_ausente_marca_doc_incompleta(monkeypatch):
    incap_id = uuid.uuid4()
    actor = uuid.uuid4()

    incap = MagicMock(spec=Incapacidad)
    incap.id = incap_id
    incap.estado = IncapacidadEstado.PROCESANDO_IA

    session = AsyncMock()
    session.get = AsyncMock(return_value=incap)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.AsyncSessionLocal",
        lambda: _fake_session_cm(session),
    )
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    settings = MagicMock()
    await run_incapacidad_extraction_job(
        incap_id, "/no/existe.pdf", actor, settings=settings
    )

    assert incap.estado == IncapacidadEstado.DOC_INCOMPLETA
    session.commit.assert_awaited_once()
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_job_error_gemini_marca_doc_incompleta(monkeypatch):
    incap_id = uuid.uuid4()
    actor = uuid.uuid4()

    incap = MagicMock(spec=Incapacidad)
    incap.id = incap_id
    incap.estado = IncapacidadEstado.PROCESANDO_IA

    session = AsyncMock()
    session.get = AsyncMock(return_value=incap)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.add = MagicMock()

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.AsyncSessionLocal",
        lambda: _fake_session_cm(session),
    )
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    async def boom(*_a, **_k):
        raise GeminiExtractionError("API")

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.extract_from_local_file",
        boom,
    )

    settings = MagicMock()
    await run_incapacidad_extraction_job(incap_id, "/z/a.pdf", actor, settings=settings)

    assert incap.estado == IncapacidadEstado.DOC_INCOMPLETA
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_job_fallo_commit_intenta_persistir_error_en_nueva_sesion(monkeypatch):
    """Tras fallo de commit, se intenta persistir doc_incompleta en otra sesión."""
    incap_id = uuid.uuid4()
    actor = uuid.uuid4()

    incap1 = MagicMock(spec=Incapacidad)
    incap1.id = incap_id
    incap1.estado = IncapacidadEstado.PROCESANDO_IA

    session1 = AsyncMock()
    session1.get = AsyncMock(return_value=incap1)
    session1.scalar = AsyncMock(return_value=None)
    session1.rollback = AsyncMock()
    session1.add = MagicMock()

    async def commit_boom(*_a, **_k):
        raise RuntimeError("commit falló")

    session1.commit = AsyncMock(side_effect=commit_boom)

    incap2 = MagicMock(spec=Incapacidad)
    incap2.id = incap_id
    incap2.estado = IncapacidadEstado.PROCESANDO_IA

    session2 = AsyncMock()
    session2.get = AsyncMock(return_value=incap2)
    session2.commit = AsyncMock()
    session2.rollback = AsyncMock()
    session2.add = MagicMock()

    cms = [_fake_session_cm(session1), _fake_session_cm(session2)]

    def next_cm():
        return cms.pop(0)

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.AsyncSessionLocal",
        next_cm,
    )
    monkeypatch.setattr(Path, "is_file", lambda self: True)

    async def fake_extract(*_a, **_k):
        return LocalExtractionResult(
            normalized={
                "paciente": None,
                "incapacidad": None,
                "diagnostico": None,
                "entidad": None,
                "medico": None,
                "documento": None,
                "validaciones": None,
            },
            raw_response="{}",
        )

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.extract_from_local_file",
        fake_extract,
    )

    settings = MagicMock()
    await run_incapacidad_extraction_job(incap_id, "/z/a.pdf", actor, settings=settings)

    session1.rollback.assert_awaited()
    assert incap2.estado == IncapacidadEstado.DOC_INCOMPLETA
    session2.commit.assert_awaited()


@pytest.mark.asyncio
async def test_job_no_op_si_estado_no_es_procesando(monkeypatch):
    incap_id = uuid.uuid4()
    actor = uuid.uuid4()

    incap = MagicMock(spec=Incapacidad)
    incap.id = incap_id
    incap.estado = IncapacidadEstado.EN_VERIFICACION

    session = AsyncMock()
    session.get = AsyncMock(return_value=incap)
    session.commit = AsyncMock()

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.AsyncSessionLocal",
        lambda: _fake_session_cm(session),
    )

    called = {"n": 0}

    async def nope(*_a, **_k):
        called["n"] += 1
        return LocalExtractionResult(normalized={}, raw_response="")

    monkeypatch.setattr(
        "app.services.incapacidad_extraction_jobs.extract_from_local_file",
        nope,
    )

    await run_incapacidad_extraction_job(incap_id, "/z/a.pdf", actor)

    assert called["n"] == 0
    session.commit.assert_not_called()
