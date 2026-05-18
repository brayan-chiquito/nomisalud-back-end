"""Tests del procesador OCR (SCRUM-166)."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

from app.services.ocr_processor import (
    OcrProcessorError,
    ResultadoProcesamientoOcr,
    TipoDocumentoOcr,
    clasificar_pdf,
    extraer_texto_pdf_nativo,
    preprocesar_imagen,
    procesar_documento,
)


def _imagen_con_texto(texto: str) -> Image.Image:
    img = Image.new("RGB", (280, 100), "white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 32), texto, fill="black")
    return img


def _png_bytes(texto: str = "ESCANEADO NOMISALUD") -> bytes:
    buf = io.BytesIO()
    _imagen_con_texto(texto).save(buf, format="PNG")
    return buf.getvalue()


def _pdf_nativo_bytes() -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(
        w=0,
        h=8,
        text=(
            "Documento nativo de prueba NomiSalud. "
            "Incapacidad laboral con texto embebido suficiente para clasificacion."
        ),
    )
    out = pdf.output()
    return bytes(out)


def test_preprocesar_imagen_es_escala_de_grises() -> None:
    img = Image.new("RGB", (40, 40), color=(200, 50, 50))
    out = preprocesar_imagen(img, factor_contraste=1.5)
    assert out.mode == "L"


def test_texto_parece_nativo_umbral() -> None:
    tipo, texto, paginas = clasificar_pdf(_pdf_nativo_bytes())
    assert tipo == TipoDocumentoOcr.NATIVO
    assert "NomiSalud" in texto
    assert paginas >= 1


def test_clasificar_pdf_vacio_como_escaneado() -> None:
    from pypdf import PdfWriter

    buf = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.write(buf)
    tipo, texto, _ = clasificar_pdf(buf.getvalue())
    assert tipo == TipoDocumentoOcr.ESCANEADO
    assert texto == ""


def test_procesar_documento_vacio() -> None:
    with pytest.raises(OcrProcessorError, match="vacío"):
        procesar_documento(b"")


def test_procesar_tipo_no_soportado() -> None:
    with pytest.raises(OcrProcessorError, match="no soportado"):
        procesar_documento(b"hola", nombre_archivo="archivo.docx")


def test_procesar_pdf_nativo() -> None:
    pdf = _pdf_nativo_bytes()
    with patch(
        "app.services.ocr_processor.clasificar_pdf",
        return_value=(TipoDocumentoOcr.NATIVO, "Texto nativo completo del PDF", 2),
    ):
        res = procesar_documento(pdf, nombre_archivo="doc.pdf")
    assert res.tipo_documento == TipoDocumentoOcr.NATIVO
    assert res.texto == "Texto nativo completo del PDF"
    assert res.paginas == 2


def test_procesar_imagen_escaneada_mock_ocr() -> None:
    with (
        patch(
            "app.services.ocr_processor.tesseract_disponible",
            return_value=True,
        ),
        patch(
            "app.services.ocr_processor._ocr_imagen",
            return_value="TEXTO OCR",
        ) as ocr_mock,
    ):
        res = procesar_documento(_png_bytes(), nombre_archivo="scan.png")
    assert res == ResultadoProcesamientoOcr(
        texto="TEXTO OCR",
        tipo_documento=TipoDocumentoOcr.ESCANEADO,
        paginas=1,
    )
    ocr_mock.assert_called_once()
    assert ocr_mock.call_args.kwargs["preprocesar"] is True


def test_procesar_pdf_escaneado_mock() -> None:
    pdf = b"%PDF-fake"
    pagina = _imagen_con_texto("PAGINA1")
    with (
        patch(
            "app.services.ocr_processor.clasificar_pdf",
            return_value=(TipoDocumentoOcr.ESCANEADO, "", 1),
        ),
        patch(
            "app.services.ocr_processor._pdf_a_imagenes",
            return_value=[pagina],
        ),
        patch(
            "app.services.ocr_processor._ocr_imagenes_paginas",
            return_value="linea uno",
        ) as pag_mock,
    ):
        res = procesar_documento(pdf, nombre_archivo="scan.pdf")
    assert res.tipo_documento == TipoDocumentoOcr.ESCANEADO
    assert res.texto == "linea uno"
    assert res.paginas == 1
    pag_mock.assert_called_once()


@pytest.mark.integration
def test_muestras_documento_nativo_y_escaneado() -> None:
    """Conjunto de muestra: PDF nativo (fpdf) e imagen PNG con OCR real."""
    from app.services.ocr_tesseract import tesseract_disponible

    pdf = _pdf_nativo_bytes()
    res_nativo = procesar_documento(pdf, nombre_archivo="muestra_nativo.pdf")
    assert res_nativo.tipo_documento == TipoDocumentoOcr.NATIVO
    assert len(res_nativo.texto) >= 40
    assert "NomiSalud" in res_nativo.texto

    if not tesseract_disponible():
        pytest.skip("Tesseract no disponible para muestra escaneada.")

    res_scan = procesar_documento(
        _png_bytes("INCAPACIDAD LABORAL"),
        nombre_archivo="muestra_escaneada.png",
        idioma="eng",
    )
    assert res_scan.tipo_documento == TipoDocumentoOcr.ESCANEADO
    normalizado = "".join(res_scan.texto.upper().split())
    assert "INCAPACIDAD" in normalizado or "LABORAL" in normalizado


@pytest.mark.integration
def test_extraer_texto_pdf_nativo_integracion() -> None:
    texto = extraer_texto_pdf_nativo(_pdf_nativo_bytes())
    assert "NomiSalud" in texto
