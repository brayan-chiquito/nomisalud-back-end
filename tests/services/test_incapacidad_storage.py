"""Tests de validación y persistencia de adjuntos de incapacidades."""

from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from app.models.incapacidad import ArchivoTipo
from app.services.incapacidad_storage import (
    IncapacidadStorageError,
    infer_archivo_tipo,
    persist_incapacidad_attachment,
)


class TestInferArchivoTipo:
    def test_pdf_por_extension(self):
        assert infer_archivo_tipo("doc.PDF", None) == ArchivoTipo.PDF

    def test_jpeg_se_normaliza_a_jpg(self):
        assert infer_archivo_tipo("foto.jpeg", "image/jpeg") == ArchivoTipo.JPG

    def test_png_con_content_type(self):
        assert infer_archivo_tipo("x.png", "image/png") == ArchivoTipo.PNG

    def test_rechaza_extension_desconocida(self):
        with pytest.raises(IncapacidadStorageError, match="no permitido"):
            infer_archivo_tipo("mal.exe", None)

    def test_rechaza_content_type_inconsistente(self):
        with pytest.raises(IncapacidadStorageError, match="Content-Type"):
            infer_archivo_tipo("x.pdf", "image/png")


@pytest.mark.asyncio
class TestPersistIncapacidadAttachment:
    async def test_escribe_archivo_y_metadatos(self, tmp_path):
        body = b"%PDF-1.4 prueba"
        up = UploadFile(
            filename="informe.pdf",
            file=BytesIO(body),
            headers={"content-type": "application/pdf"},
        )
        path, file_uuid, tipo, tam = await persist_incapacidad_attachment(
            up,
            base_dir=tmp_path,
            max_bytes=1024,
        )
        assert tipo == ArchivoTipo.PDF
        assert tam == len(body)
        assert path.name == f"{file_uuid}.pdf"
        assert path.read_bytes() == body

    async def test_rechaza_vacio(self, tmp_path):
        up = UploadFile(
            filename="vacio.pdf",
            file=BytesIO(b""),
            headers={"content-type": "application/pdf"},
        )
        with pytest.raises(IncapacidadStorageError, match="vacío"):
            await persist_incapacidad_attachment(
                up, base_dir=tmp_path, max_bytes=1024
            )

    async def test_rechaza_si_supera_maximo(self, tmp_path):
        up = UploadFile(
            filename="g.pdf",
            file=BytesIO(b"x" * 500),
            headers={"content-type": "application/pdf"},
        )
        with pytest.raises(IncapacidadStorageError, match="tamaño máximo"):
            await persist_incapacidad_attachment(
                up, base_dir=tmp_path, max_bytes=100
            )


def test_radicado_candidato_longitud_y_prefijo():
    from app.services.incapacidad_upload_service import _new_radicado_candidate

    r = _new_radicado_candidate()
    assert len(r) == 20
    assert r.startswith("IN")
    uuid_part = r[2:]
    assert len(uuid_part) == 18
    assert uuid_part == uuid_part.upper()
