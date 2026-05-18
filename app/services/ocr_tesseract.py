"""Extracción de texto con Tesseract OCR y Pillow (SCRUM-165)."""

from __future__ import annotations

import io
import shutil
from typing import BinaryIO

import pytesseract
from PIL import Image

from app.core.config import get_settings


def tesseract_disponible() -> bool:
    """Indica si el binario de Tesseract está accesible en el entorno."""
    settings = get_settings()
    if settings.TESSERACT_CMD:
        return shutil.which(settings.TESSERACT_CMD) is not None
    return shutil.which("tesseract") is not None


def _configurar_pytesseract() -> None:
    cmd = get_settings().TESSERACT_CMD
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd


def extraer_texto_de_imagen(
    imagen: bytes | BinaryIO | Image.Image,
    *,
    idioma: str | None = None,
) -> str:
    """
    Ejecuta OCR sobre una imagen y devuelve el texto reconocido (trim aplicado).

    Raises:
        RuntimeError: si Tesseract no está instalado o no está en PATH.
        pytesseract.TesseractError: si el motor OCR falla al procesar la imagen.
    """
    if not tesseract_disponible():
        raise RuntimeError(
            "Tesseract no está instalado o no está en PATH. "
            "En Docker, use la imagen con los paquetes tesseract-ocr."
        )

    _configurar_pytesseract()
    lang = idioma or get_settings().TESSERACT_LANG

    if isinstance(imagen, Image.Image):
        return pytesseract.image_to_string(imagen, lang=lang).strip()

    fuente = io.BytesIO(imagen) if isinstance(imagen, bytes) else imagen
    with Image.open(fuente) as pil:
        return pytesseract.image_to_string(pil, lang=lang).strip()
