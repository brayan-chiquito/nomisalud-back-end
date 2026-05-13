"""Tests GET /api/v1/incapacidades/{id} y descarga de archivo (SCRUM-133)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.extraccion_ia import CalidadDocumento, ExtraccionIA
from app.models.incapacidad import ArchivoTipo, Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.services.incapacidad_detail_service import IncapacidadDetalleBundle


def _token(role: UserRole, user_id: uuid.UUID | None = None) -> tuple[str, uuid.UUID]:
    uid = user_id or uuid.uuid4()
    return (
        create_access_token(
            uid,
            role.value,
            f"user-{uid.hex[:8]}@test.local",
        ),
        uid,
    )


def _bundle(
    colaborador_id: uuid.UUID,
    *,
    con_archivo: bool = True,
    con_extraccion: bool = True,
) -> IncapacidadDetalleBundle:
    iid = uuid.uuid4()
    inc = MagicMock(spec=Incapacidad)
    inc.id = iid
    inc.radicado = "IN0123456789ABCDEF0"
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.colaborador_id = colaborador_id
    inc.cargado_por = colaborador_id
    inc.user_id = colaborador_id
    inc.archivo_uuid = str(uuid.uuid4())
    inc.archivo_path = "/fake/path/doc.pdf" if con_archivo else None
    inc.archivo_tipo = ArchivoTipo.PDF
    inc.archivo_tamano_bytes = 100
    inc.documentacion_faltante = None
    inc.fecha_recepcion = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)
    inc.created_at = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)
    inc.updated_at = datetime(2025, 5, 1, 10, 0, tzinfo=UTC)

    ext = None
    if con_extraccion:
        ext = MagicMock(spec=ExtraccionIA)
        ext.id = uuid.uuid4()
        ext.incapacidad_id = iid
        ext.datos_extraidos = {"paciente": {"nombre_completo": "Test"}}
        ext.campos_corregidos = None
        ext.validaciones = None
        ext.raw_response = "{}"
        ext.api_usada = "google"
        ext.modelo = "gemini-2.5-flash"
        ext.tokens_input = 1
        ext.tokens_output = 2
        ext.costo_usd = None
        ext.calidad_doc = CalidadDocumento.BUENA
        ext.verificado_por = None
        ext.verificado_en = None
        ext.created_at = datetime(2025, 5, 1, 10, 1, tzinfo=UTC)

    return IncapacidadDetalleBundle(
        incapacidad=inc,
        extraccion_ia=ext,
        colaborador_nombre="Colab Uno",
        colaborador_email="colab@test.local",
    )


@pytest.mark.asyncio
class TestIncapacidadDetalleGet:
    async def test_404_si_no_existe(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        iid = uuid.uuid4()
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{iid}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 404

    async def test_403_colaborador_ve_otro(self, client: AsyncClient):
        token, _ = _token(UserRole.COLABORADOR, uuid.uuid4())
        otro = uuid.uuid4()
        bundle = _bundle(otro)
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=bundle,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 403

    async def test_200_con_extraccion_y_archivo_url(self, client: AsyncClient):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        bundle = _bundle(uid)
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=bundle,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["radicado"] == "IN0123456789ABCDEF0"
        assert body["estado"] == "en_verificacion"
        assert body["colaborador_nombre"] == "Colab Uno"
        assert body["extraccion_ia"] is not None
        pac = body["extraccion_ia"]["datos_extraidos"]["paciente"]
        assert pac["nombre_completo"] == "Test"
        assert body["extraccion_ia"]["calidad_doc"] == "buena"
        assert "/archivo" in (body["archivo_url"] or "")

    async def test_extraccion_costo_usd_serializado(self, client: AsyncClient):
        token, uid = _token(UserRole.ADMIN)
        bundle = _bundle(uid)
        assert bundle.extraccion_ia is not None
        bundle.extraccion_ia.costo_usd = Decimal("0.001234")
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=bundle,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        assert r.json()["extraccion_ia"]["costo_usd"] == pytest.approx(0.001234)

    async def test_200_sin_extraccion_archivo_url_null(self, client: AsyncClient):
        token, uid = _token(UserRole.ADMIN)
        bundle = _bundle(uid, con_extraccion=False, con_archivo=False)
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=bundle,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["extraccion_ia"] is None
        assert body["archivo_url"] is None


@pytest.mark.asyncio
class TestIncapacidadArchivoDownload:
    async def test_404_incapacidad_no_existe(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        iid = uuid.uuid4()
        with patch(
            "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
            new_callable=AsyncMock,
            return_value=None,
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{iid}/archivo",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 404

    async def test_404_si_sin_archivo_en_disco(self, client: AsyncClient):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        bundle = _bundle(uid, con_archivo=True)
        with (
            patch(
                "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
                new_callable=AsyncMock,
                return_value=bundle,
            ),
            patch(
                "app.api.v1.routes.incapacidades.resolve_archivo_under_storage",
                return_value=None,
            ),
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}/archivo",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 404

    async def test_200_descarga(self, client: AsyncClient, tmp_path: Path):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        bundle = _bundle(uid, con_archivo=True)
        fake_file = tmp_path / "f.pdf"
        fake_file.write_bytes(b"%PDF-1.4 test")
        with (
            patch(
                "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
                new_callable=AsyncMock,
                return_value=bundle,
            ),
            patch(
                "app.api.v1.routes.incapacidades.resolve_archivo_under_storage",
                return_value=fake_file,
            ),
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}/archivo",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        assert r.content == b"%PDF-1.4 test"
        assert "application/pdf" in (r.headers.get("content-type") or "")

    async def test_descarga_sin_archivo_tipo_usa_extension(
        self, client: AsyncClient, tmp_path: Path
    ):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        bundle = _bundle(uid, con_archivo=True)
        bundle.incapacidad.archivo_tipo = None
        fake_file = tmp_path / "f.png"
        fake_file.write_bytes(b"\x89PNG\r\n")
        with (
            patch(
                "app.api.v1.routes.incapacidades.get_incapacidad_detalle",
                new_callable=AsyncMock,
                return_value=bundle,
            ),
            patch(
                "app.api.v1.routes.incapacidades.resolve_archivo_under_storage",
                return_value=fake_file,
            ),
        ):
            r = await client.get(
                f"/api/v1/incapacidades/{bundle.incapacidad.id}/archivo",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        assert "image/png" in (r.headers.get("content-type") or "")
