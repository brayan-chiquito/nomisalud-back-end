"""Prompt de extracción con contexto OCR (SCRUM-167)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.services import ai_extractor
from app.services.ai_extractor import (
    build_extraction_prompt,
    extract_from_local_file,
    load_extraction_prompt,
    normalize_extraccion_json,
    texto_ocr_disponible,
)

_OCR_MUESTRA = (
    "PACIENTE: Maria Lopez Garcia. CC 5298765432. EPS Sura. "
    "Incapacidad laboral 10 dias desde 2026-06-01 hasta 2026-06-10."
)


def _campos_minimos(normalized: dict[str, Any]) -> int:
    n = 0
    paciente = normalized.get("paciente")
    incapacidad = normalized.get("incapacidad")
    entidad = normalized.get("entidad")
    if isinstance(paciente, dict):
        if paciente.get("nombre_completo"):
            n += 1
        if paciente.get("numero_documento"):
            n += 1
    if isinstance(incapacidad, dict):
        for key in ("total_dias", "fecha_inicio", "fecha_fin", "tipo"):
            if incapacidad.get(key) is not None:
                n += 1
    if isinstance(entidad, dict) and entidad.get("nombre"):
        n += 1
    return n


def test_texto_ocr_disponible() -> None:
    assert texto_ocr_disponible("  hola  ") is True
    assert texto_ocr_disponible("") is False
    assert texto_ocr_disponible("   ") is False
    assert texto_ocr_disponible(None) is False


def test_build_prompt_sin_ocr_omite_seccion() -> None:
    base = load_extraction_prompt()
    out = build_extraction_prompt(None)
    assert "{{OCR_TEXTO}}" not in out
    assert "CONTEXTO ADICIONAL — TEXTO OCR" not in out
    assert len(out) < len(base)


def test_build_prompt_con_ocr_inyecta_texto() -> None:
    out = build_extraction_prompt(_OCR_MUESTRA)
    assert "CONTEXTO ADICIONAL — TEXTO OCR" in out
    assert _OCR_MUESTRA in out
    assert "{{OCR_TEXTO}}" not in out


@pytest.mark.asyncio
async def test_extract_envia_prompt_con_ocr_en_body(tmp_path, monkeypatch) -> None:
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")
    capturado: dict[str, str] = {}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            capturado["prompt"] = kwargs["json"]["contents"][0]["parts"][0]["text"]
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": "{}"}]}}]
            }
            return r

    monkeypatch.setattr(ai_extractor.httpx, "AsyncClient", lambda *a, **k: FakeClient())

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 1
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    await extract_from_local_file(f, settings=settings, texto_ocr=_OCR_MUESTRA)
    assert _OCR_MUESTRA in capturado["prompt"]
    assert "CONTEXTO ADICIONAL — TEXTO OCR" in capturado["prompt"]


@pytest.mark.asyncio
async def test_comparativo_ocr_incrementa_campos_minimos(tmp_path, monkeypatch) -> None:
    """
    Con el mismo archivo, el prompt con OCR guía una respuesta más completa
    (simulada) que la versión base sin contexto OCR.
    """
    f = tmp_path / "a.pdf"
    f.write_bytes(b"%PDF-1.4")

    escaso = {
        "paciente": {"nombre_completo": None, "numero_documento": None},
        "incapacidad": {
            "tipo": None,
            "fecha_inicio": None,
            "fecha_fin": None,
            "total_dias": None,
        },
        "entidad": {"nombre": None},
        "diagnostico": None,
        "medico": None,
        "documento": None,
        "validaciones": None,
    }
    rico = {
        "paciente": {
            "nombre_completo": "Maria Lopez Garcia",
            "numero_documento": "5298765432",
        },
        "incapacidad": {
            "tipo": "enfermedad_general",
            "fecha_inicio": "2026-06-01",
            "fecha_fin": "2026-06-10",
            "total_dias": 10,
        },
        "entidad": {"nombre": "EPS Sura"},
        "diagnostico": None,
        "medico": None,
        "documento": None,
        "validaciones": None,
    }

    class FakeClient:
        def __init__(self) -> None:
            self.last_prompt = ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            self.last_prompt = kwargs["json"]["contents"][0]["parts"][0]["text"]
            payload = rico if "Maria Lopez" in self.last_prompt else escaso
            r = MagicMock()
            r.status_code = 200
            r.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}]
            }
            return r

    client = FakeClient()
    monkeypatch.setattr(
        ai_extractor.httpx,
        "AsyncClient",
        lambda *a, **k: client,
    )

    settings = MagicMock()
    settings.GEMINI_API_KEY = "k"
    settings.GEMINI_EXTRACTION_MAX_ATTEMPTS = 1
    settings.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS = 0.01
    settings.GEMINI_HTTP_TIMEOUT_SECONDS = 30.0

    sin_ocr = await extract_from_local_file(
        f, settings=settings, texto_ocr=None
    )
    con_ocr = await extract_from_local_file(
        f, settings=settings, texto_ocr=_OCR_MUESTRA
    )

    campos_sin = _campos_minimos(normalize_extraccion_json(sin_ocr.normalized))
    campos_con = _campos_minimos(normalize_extraccion_json(con_ocr.normalized))

    assert campos_sin == 0
    assert campos_con >= 5
    assert campos_con > campos_sin
