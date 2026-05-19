"""Tests del extractor IA (Gemini) — SCRUM-125 / SCRUM-126."""

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services import ai_extractor
from app.services.ai_extractor import (
    GeminiExtractionError,
    LocalExtractionResult,
    extract_from_local_file,
    load_extraction_prompt,
    normalize_extraccion_json,
    parse_inconsistencias_desde_extraccion,
    read_file_as_base64,
)


def _campos_minimos_scrum126(normalized: dict[str, Any]) -> int:
    """Siete campos conceptuales del ticket, mapeados al esquema anidado."""
    n = 0
    paciente = normalized.get("paciente")
    incapacidad = normalized.get("incapacidad")
    entidad = normalized.get("entidad")
    if isinstance(paciente, dict):
        if paciente.get("nombre_completo") is not None:
            n += 1
        if paciente.get("numero_documento") is not None:
            n += 1
    if isinstance(incapacidad, dict):
        for key in ("total_dias", "fecha_inicio", "fecha_fin", "tipo"):
            if incapacidad.get(key) is not None:
                n += 1
    if isinstance(entidad, dict) and entidad.get("nombre") is not None:
        n += 1
    return n


@pytest.mark.asyncio
async def test_read_file_as_base64_pdf(tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 prueba")
    b64, mime = await read_file_as_base64(f)
    assert mime == "application/pdf"
    assert isinstance(b64, str)
    assert len(b64) > 0


def test_normalize_extraccion_json_completa_y_parcial():
    assert normalize_extraccion_json("no-es-dict") == {
        "paciente": None,
        "incapacidad": None,
        "diagnostico": None,
        "entidad": None,
        "medico": None,
        "documento": None,
        "validaciones": None,
    }

    data = normalize_extraccion_json(
        {"paciente": {"nombre": "Ana"}, "diagnostico": "gripe"}
    )
    assert data["paciente"] == {"nombre": "Ana"}
    assert data["diagnostico"] == "gripe"
    assert data["incapacidad"] is None
    assert data["validaciones"] is None


def test_load_extraction_prompt_existe():
    txt = load_extraction_prompt()
    assert "paciente" in txt
    assert "validaciones" in txt
    assert "inconsistencias" in txt
    assert "Gemini 2.5 Flash" in txt
    assert "paciente.nombre_completo" in txt


def test_parse_inconsistencias_desde_extraccion_en_local_result():
    payload = {
        "inconsistencias": [
            {"tipo": "genero_tipo", "descripcion": "maternidad con genero M"},
            {"tipo": "legibilidad", "descripcion": "sello ilegible"},
        ]
    }
    out = parse_inconsistencias_desde_extraccion(payload)
    assert len(out) == 2
    assert out[0].tipo == "genero_tipo"


def test_campos_minimos_scrum126_ejemplo_completo_supera_umbral():
    """Documento bien extraído: ≥5 campos mínimos no nulos (SCRUM-126)."""
    payload = {
        "paciente": {
            "nombre_completo": "CARLOS ANDRES MARTINEZ LOPEZ",
            "numero_documento": "1098765432",
        },
        "incapacidad": {
            "tipo": "enfermedad_general",
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-05-07",
            "total_dias": 7,
        },
        "entidad": {"nombre": "EPS Sanitas"},
        "diagnostico": None,
        "medico": None,
        "documento": None,
        "validaciones": None,
    }
    out = normalize_extraccion_json(payload)
    assert _campos_minimos_scrum126(out) >= 5
    assert _campos_minimos_scrum126(out) == 7


@pytest.mark.asyncio
async def test_extraccion_mock_cumple_umbral_campos_minimos(tmp_path, monkeypatch):
    """Parseo HTTP: si el modelo envía datos, hay ≥5 campos mínimos (SCRUM-126)."""
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(ai_extractor, "load_extraction_prompt", lambda: "prompt")

    rich = {
        "paciente": {
            "nombre_completo": "ANA",
            "numero_documento": "1",
        },
        "incapacidad": {
            "tipo": "enfermedad_general",
            "fecha_inicio": "2026-01-01",
            "fecha_fin": "2026-01-05",
            "total_dias": 5,
        },
        "entidad": {"nombre": "EPS X"},
    }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(rich)}]}}]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 2
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    out = await extract_from_local_file(f, settings=settings)
    assert isinstance(out, LocalExtractionResult)
    assert _campos_minimos_scrum126(out.normalized) >= 5


@pytest.mark.asyncio
async def test_extract_retries_http_503_y_luego_ok(tmp_path, monkeypatch):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(ai_extractor, "load_extraction_prompt", lambda: "prompt")
    monkeypatch.setattr(ai_extractor, "_sleep_backoff", AsyncMock())

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                r = MagicMock()
                r.status_code = 503
                r.text = "unavailable"
                return r
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": json.dumps({"paciente": {"nombre": "Ana"}})}
                            ]
                        }
                    }
                ]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "clave-prueba"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 3
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    out = await extract_from_local_file(f, settings=settings)
    assert out.normalized["paciente"] == {"nombre": "Ana"}
    assert out.normalized["incapacidad"] is None
    assert out.normalized["validaciones"] is None


@pytest.mark.asyncio
async def test_extract_retries_transport_error(tmp_path, monkeypatch):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(ai_extractor, "load_extraction_prompt", lambda: "prompt")
    monkeypatch.setattr(ai_extractor, "_sleep_backoff", AsyncMock())

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("boom", request=MagicMock())
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "clave-prueba"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 3
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    out = await extract_from_local_file(f, settings=settings)
    assert out.normalized["paciente"] is None
    assert out.normalized["validaciones"] is None


@pytest.mark.asyncio
async def test_extract_raw_response_conserva_texto_del_modelo(tmp_path, monkeypatch):
    """raw_response guarda la salida tal cual; el parseo usa texto sin fences."""
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(ai_extractor, "load_extraction_prompt", lambda: "prompt")

    raw_wrapped = '```json\n{"paciente": {"nombre": "Z"}}\n```'

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": raw_wrapped}]}}]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 2
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    out = await extract_from_local_file(f, settings=settings)
    assert isinstance(out, LocalExtractionResult)
    assert out.raw_response == raw_wrapped
    assert out.normalized["paciente"] == {"nombre": "Z"}


@pytest.mark.asyncio
async def test_extract_falla_si_json_invalido(tmp_path, monkeypatch):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")

    monkeypatch.setattr(ai_extractor, "load_extraction_prompt", lambda: "prompt")

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [
                    {"content": {"parts": [{"text": "```json\nnot-json\n```"}]}}
                ]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "clave-prueba"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 2
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    with pytest.raises(GeminiExtractionError, match="JSON"):
        await extract_from_local_file(f, settings=settings)


@pytest.mark.asyncio
async def test_extract_falta_api_key(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")

    settings = MagicMock()
    settings.GEMINI_API_KEY = None

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        await extract_from_local_file(f, settings=settings)
