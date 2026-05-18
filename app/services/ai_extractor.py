"""
Extracción estructurada con Google Gemini (modelo fijo gemini-2.5-flash).

Lee un archivo local, lo codifica en Base64, invoca la API REST de Gemini y
normaliza la salida JSON.

El contrato usa objetos anidados (paciente, incapacidad, entidad, …) alineados al
JSONB del dominio; equivale a los campos mínimos nombre / identificación / días /
fechas / tipo / entidad del ticket SCRUM-126 sin aplanar claves en la raíz.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_PROMPT_PATH: Final[Path] = (
    _REPO_ROOT / "app" / "prompts" / "Nomisalud_prompt_extraccion.md"
)

_GEMINI_MODEL_FLASH_2_5: Final[str] = "gemini-2.5-flash"

_GEMINI_GENERATE_URL: Final[str] = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{_GEMINI_MODEL_FLASH_2_5}:generateContent"
)

_OCR_PLACEHOLDER: Final[str] = "{{OCR_TEXTO}}"
_OCR_SECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\n━+\nCONTEXTO ADICIONAL — TEXTO OCR\n━+\n\n.*?\n\n\{\{OCR_TEXTO\}\}\n",
    re.DOTALL,
)

_ROOT_KEYS: Final[tuple[str, ...]] = (
    "paciente",
    "incapacidad",
    "diagnostico",
    "entidad",
    "medico",
    "documento",
    "validaciones",
)


class GeminiExtractionError(Exception):
    """Error controlado al extraer con Gemini (respuesta inválida o API)."""


@dataclass(frozen=True)
class LocalExtractionResult:
    """Salida normalizada lista para BD y texto crudo devuelto por el modelo."""

    normalized: dict[str, Any | None]
    raw_response: str


def _guess_mime_type(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")


def load_extraction_prompt() -> str:
    """Carga el prompt desde `app/prompts/Nomisalud_prompt_extraccion.md`."""
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeminiExtractionError(
            f"No se pudo leer el archivo de prompt: {_PROMPT_PATH}"
        ) from exc


def texto_ocr_disponible(texto_ocr: str | None) -> bool:
    """True si hay texto OCR no vacío para inyectar en el prompt."""
    return bool(texto_ocr and texto_ocr.strip())


def build_extraction_prompt(texto_ocr: str | None = None) -> str:
    """
    Ensambla el prompt de extracción.

    Si ``texto_ocr`` está disponible, reemplaza ``{{OCR_TEXTO}}`` en la sección
    designada; si no, omite por completo el bloque de contexto OCR.
    """
    base = load_extraction_prompt()
    match = _OCR_SECTION_PATTERN.search(base)
    if match is None:
        if texto_ocr_disponible(texto_ocr):
            return f"{base.rstrip()}\n\n{_OCR_PLACEHOLDER}\n".replace(
                _OCR_PLACEHOLDER, texto_ocr.strip()
            )
        return base

    if not texto_ocr_disponible(texto_ocr):
        return base[: match.start()] + "\n" + base[match.end() :]

    bloque = match.group(0).replace(_OCR_PLACEHOLDER, texto_ocr.strip())
    return base[: match.start()] + bloque + base[match.end() :]


async def read_file_as_base64(file_path: str | Path) -> tuple[str, str]:
    """
    Lee bytes del archivo en disco y devuelve (base64, mime_type inferido).
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    def _read() -> bytes:
        return path.read_bytes()

    raw = await asyncio.to_thread(_read)
    if not raw:
        raise ValueError("El archivo está vacío.")

    encoded = base64.b64encode(raw).decode("ascii")
    return encoded, _guess_mime_type(path)


def normalize_extraccion_json(data: Any) -> dict[str, Any | None]:
    """
    Garantiza las claves raíz requeridas; valores ausentes o tipos inesperados → null.
    """
    if not isinstance(data, dict):
        return dict.fromkeys(_ROOT_KEYS, None)
    return {k: data.get(k) for k in _ROOT_KEYS}


def _strip_json_fences(text: str) -> str:
    """
    Quita fences tipo markdown sin regex ambiguos (evita ReDoS, Sonar S5852).
    """
    raw = text.strip()
    if not raw.startswith("```"):
        return raw
    body = raw[3:]
    i = 0
    while (
        i < len(body)
        and body[i]
        in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    ):
        i += 1
    while i < len(body) and body[i] in " \t":
        i += 1
    if i < len(body) and body[i] == "\r":
        i += 1
    if i < len(body) and body[i] == "\n":
        i += 1
    body = body[i:]
    body = body.rstrip()
    if body.endswith("```"):
        body = body[:-3].rstrip()
    return body


def _extract_model_text(payload: dict[str, Any]) -> str:
    try:
        candidates = payload["candidates"]
        content = candidates[0]["content"]
        parts = content["parts"]
        return str(parts[0]["text"])
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiExtractionError(
            "Respuesta de Gemini sin texto en el formato esperado."
        ) from exc


def _should_retry_status(status_code: int) -> bool:
    if status_code == 429:
        return True
    return status_code >= 500


async def _sleep_backoff(base_seconds: float, attempt_index: int) -> None:
    delay = base_seconds * (2**attempt_index)
    await asyncio.sleep(delay)


def _local_extraction_from_gemini_payload(
    payload: dict[str, Any],
) -> LocalExtractionResult:
    raw_response = _extract_model_text(payload)
    to_parse = _strip_json_fences(raw_response.strip())
    try:
        parsed = json.loads(to_parse)
    except json.JSONDecodeError as exc:
        raise GeminiExtractionError(
            "La respuesta del modelo no es JSON válido."
        ) from exc
    return LocalExtractionResult(
        normalized=normalize_extraccion_json(parsed),
        raw_response=raw_response,
    )


async def extract_from_local_file(
    file_path: str | Path,
    *,
    settings: Settings | None = None,
    mime_type: str | None = None,
    texto_ocr: str | None = None,
) -> LocalExtractionResult:
    """
    Extrae información estructurada desde un archivo local usando Gemini.

    Reintenta ante fallos de red y algunos códigos HTTP transitorios.
    Devuelve el JSON normalizado y el texto crudo del modelo (antes de recortar
    fences), útil para auditoría / columna `raw_response` en BD.
    """
    cfg = settings or get_settings()
    if not cfg.GEMINI_API_KEY:
        raise ValueError("Falta GEMINI_API_KEY en la configuración.")

    b64, guessed_mime = await read_file_as_base64(file_path)
    mime = (mime_type or guessed_mime).strip()

    prompt = build_extraction_prompt(texto_ocr)
    url = _GEMINI_GENERATE_URL
    params = {"key": cfg.GEMINI_API_KEY}

    body: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": mime, "data": b64}},
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2,
        },
    }

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(cfg.GEMINI_HTTP_TIMEOUT_SECONDS)
    ) as client:
        for attempt in range(cfg.GEMINI_EXTRACTION_MAX_ATTEMPTS):
            try:
                resp = await client.post(url, params=params, json=body)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt + 1 < cfg.GEMINI_EXTRACTION_MAX_ATTEMPTS:
                    logger.warning(
                        "Fallo de red con Gemini (%s). Reintentando…",
                        type(exc).__name__,
                    )
                    await _sleep_backoff(
                        cfg.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS, attempt
                    )
                    continue
                raise GeminiExtractionError(
                    "No se pudo completar la extracción tras reintentos."
                ) from exc

            if resp.status_code == 200:
                return _local_extraction_from_gemini_payload(resp.json())

            if _should_retry_status(resp.status_code) and attempt + 1 < (
                cfg.GEMINI_EXTRACTION_MAX_ATTEMPTS
            ):
                logger.warning(
                    "Gemini HTTP %s (intento %s/%s). Reintentando…",
                    resp.status_code,
                    attempt + 1,
                    cfg.GEMINI_EXTRACTION_MAX_ATTEMPTS,
                )
                await _sleep_backoff(
                    cfg.GEMINI_EXTRACTION_BACKOFF_BASE_SECONDS, attempt
                )
                continue

            raise GeminiExtractionError(
                f"Error HTTP de Gemini: {resp.status_code} — {resp.text[:500]}"
            )
