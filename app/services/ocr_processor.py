"""OCR: clasificación nativo/escaneado, pre-procesado y extracción (SCRUM-166)."""

from __future__ import annotations

import enum
import io
import re
from dataclasses import dataclass

from PIL import Image, ImageEnhance, ImageOps
from pypdf import PdfReader

from app.core.config import get_settings
from app.services.ocr_tesseract import extraer_texto_de_imagen, tesseract_disponible

_EXTENSIONES_IMAGEN = frozenset({"jpg", "jpeg", "png"})


class TipoDocumentoOcr(str, enum.Enum):
    """Origen del documento respecto a la extracción de texto."""

    NATIVO = "nativo"
    ESCANEADO = "escaneado"


class OcrProcessorError(Exception):
    """Error de negocio del procesador OCR."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass(frozen=True)
class ResultadoProcesamientoOcr:
    """Salida íntegra del procesamiento."""

    texto: str
    tipo_documento: TipoDocumentoOcr
    paginas: int


def _extension_desde_nombre(nombre_archivo: str | None) -> str:
    if not nombre_archivo or "." not in nombre_archivo:
        return ""
    return nombre_archivo.rsplit(".", 1)[-1].lower().strip()


def _texto_parece_nativo(texto: str) -> bool:
    """Heurística: PDF con capa de texto suficiente y legible."""
    limpio = re.sub(r"\s+", " ", texto).strip()
    settings = get_settings()
    if len(limpio) < settings.OCR_MIN_CHARS_PDF_NATIVO:
        return False
    alnum = sum(1 for c in limpio if c.isalnum())
    return alnum / len(limpio) >= 0.25


def extraer_texto_pdf_nativo(
    contenido: bytes,
    reader: PdfReader | None = None,
) -> str:
    """Extrae texto embebido de un PDF digital (sin OCR)."""
    pdf = reader or PdfReader(io.BytesIO(contenido))
    partes: list[str] = []
    for page in pdf.pages:
        fragmento = page.extract_text()
        if fragmento:
            partes.append(fragmento)
    return "\n".join(partes).strip()


def clasificar_pdf(contenido: bytes) -> tuple[TipoDocumentoOcr, str, int]:
    """
    Determina si el PDF es nativo (texto embebido) o escaneado (requiere OCR).

    Returns:
        ``(tipo, texto_nativo, paginas)``; si es escaneado, ``texto_nativo`` vacío.
    """
    try:
        reader = PdfReader(io.BytesIO(contenido))
        paginas = len(reader.pages)
        texto = extraer_texto_pdf_nativo(contenido, reader=reader)
    except Exception as exc:
        raise OcrProcessorError(f"No se pudo leer el PDF: {exc}") from exc

    if _texto_parece_nativo(texto):
        return TipoDocumentoOcr.NATIVO, texto, paginas
    return TipoDocumentoOcr.ESCANEADO, "", paginas


def preprocesar_imagen(
    imagen: Image.Image,
    *,
    factor_contraste: float | None = None,
) -> Image.Image:
    """Escala de grises y mejora de contraste para optimizar el OCR."""
    if factor_contraste is None:
        factor = get_settings().OCR_CONTRAST_FACTOR
    else:
        factor = factor_contraste
    gris = ImageOps.grayscale(imagen)
    return ImageEnhance.Contrast(gris).enhance(factor)


def _pdf_a_imagenes(contenido: bytes) -> list[Image.Image]:
    from pdf2image import convert_from_bytes

    dpi = get_settings().OCR_PDF_RENDER_DPI
    return convert_from_bytes(contenido, dpi=dpi)


def _ocr_imagen(
    imagen: Image.Image,
    *,
    idioma: str | None,
    preprocesar: bool,
) -> str:
    if not tesseract_disponible():
        raise OcrProcessorError(
            "Tesseract no está disponible; no se puede OCR un documento escaneado."
        )
    lista = preprocesar_imagen(imagen) if preprocesar else imagen
    return extraer_texto_de_imagen(lista, idioma=idioma)


def _ocr_imagenes_paginas(
    imagenes: list[Image.Image],
    *,
    idioma: str | None,
) -> str:
    fragmentos: list[str] = []
    for img in imagenes:
        texto = _ocr_imagen(img, idioma=idioma, preprocesar=True)
        if texto:
            fragmentos.append(texto)
    return "\n\n".join(fragmentos).strip()


def procesar_documento(
    contenido: bytes,
    *,
    nombre_archivo: str | None = None,
    idioma: str | None = None,
) -> ResultadoProcesamientoOcr:
    """
    Evalúa el documento, aplica pre-procesado si corresponde y devuelve el texto.

    - **PDF nativo:** extracción directa con ``pypdf``.
    - **PDF escaneado / imágenes:** render o apertura + gris/contraste + Tesseract.

    Raises:
        OcrProcessorError: tipo no soportado o fallo de lectura/OCR.
    """
    if not contenido:
        raise OcrProcessorError("El documento está vacío.")

    ext = _extension_desde_nombre(nombre_archivo)

    if ext in _EXTENSIONES_IMAGEN:
        with Image.open(io.BytesIO(contenido)) as img:
            texto = _ocr_imagen(img, idioma=idioma, preprocesar=True)
        return ResultadoProcesamientoOcr(
            texto=texto,
            tipo_documento=TipoDocumentoOcr.ESCANEADO,
            paginas=1,
        )

    if ext == "pdf" or contenido.startswith(b"%PDF"):
        tipo, texto_nativo, num_paginas = clasificar_pdf(contenido)
        if tipo == TipoDocumentoOcr.NATIVO:
            return ResultadoProcesamientoOcr(
                texto=texto_nativo,
                tipo_documento=TipoDocumentoOcr.NATIVO,
                paginas=num_paginas,
            )

        imagenes = _pdf_a_imagenes(contenido)
        if not imagenes:
            raise OcrProcessorError("El PDF no contiene páginas renderizables.")
        texto = _ocr_imagenes_paginas(imagenes, idioma=idioma)
        return ResultadoProcesamientoOcr(
            texto=texto,
            tipo_documento=TipoDocumentoOcr.ESCANEADO,
            paginas=len(imagenes),
        )

    raise OcrProcessorError("Tipo de documento no soportado. Use PDF, JPG/JPEG o PNG.")
