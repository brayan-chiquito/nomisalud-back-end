"""Tests de OCR con Tesseract (SCRUM-165)."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr_tesseract import (
    extraer_texto_de_imagen,
    tesseract_disponible,
)


def _imagen_con_texto(texto: str) -> Image.Image:
    img = Image.new("RGB", (240, 90), "white")
    draw = ImageDraw.Draw(img)
    draw.text((16, 28), texto, fill="black")
    return img


def test_tesseract_disponible_es_bool() -> None:
    assert isinstance(tesseract_disponible(), bool)


def test_extraer_texto_sin_tesseract_lanza_runtime_error() -> None:
    with patch(
        "app.services.ocr_tesseract.tesseract_disponible",
        return_value=False,
    ):
        with pytest.raises(RuntimeError, match="Tesseract no está instalado"):
            extraer_texto_de_imagen(b"not-an-image")


def test_extraer_texto_con_mock_pytesseract() -> None:
    img = _imagen_con_texto("TEST")
    with (
        patch(
            "app.services.ocr_tesseract.tesseract_disponible",
            return_value=True,
        ),
        patch(
            "app.services.ocr_tesseract.pytesseract.image_to_string",
            return_value="  linea NOMISALUD  \n",
        ) as ocr_mock,
    ):
        texto = extraer_texto_de_imagen(img, idioma="eng")
    assert texto == "linea NOMISALUD"
    ocr_mock.assert_called_once()
    assert ocr_mock.call_args.kwargs["lang"] == "eng"


def test_extraer_texto_desde_bytes() -> None:
    img = _imagen_con_texto("BYTES")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    payload = buf.getvalue()

    with (
        patch(
            "app.services.ocr_tesseract.tesseract_disponible",
            return_value=True,
        ),
        patch(
            "app.services.ocr_tesseract.pytesseract.image_to_string",
            return_value="BYTES OK",
        ),
    ):
        assert extraer_texto_de_imagen(payload, idioma="eng") == "BYTES OK"


@pytest.mark.integration
@pytest.mark.skipif(
    not tesseract_disponible(),
    reason="Tesseract no instalado en este entorno (requerido en Docker).",
)
def test_ocr_imagen_sintetica_en_contenedor() -> None:
    """Valida el motor OCR real (típico en la imagen Docker con tesseract-ocr)."""
    texto = extraer_texto_de_imagen(_imagen_con_texto("NOMISALUD"), idioma="eng")
    normalizado = "".join(texto.upper().split())
    assert "NOMISALUD" in normalizado


@pytest.mark.integration
@pytest.mark.skipif(
    not tesseract_disponible(),
    reason="Tesseract no instalado en este entorno.",
)
def test_tesseract_version_accesible() -> None:
    import pytesseract

    version = pytesseract.get_tesseract_version()
    assert version is not None
    assert str(version) != ""
