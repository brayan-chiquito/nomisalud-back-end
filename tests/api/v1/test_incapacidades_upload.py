"""Tests del endpoint POST /api/v1/incapacidades/upload."""

import errno
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole


def _token(role: UserRole, user_id: uuid.UUID | None = None) -> str:
    uid = user_id or uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"user-{uid.hex[:8]}@test.local",
    ), uid


@pytest.mark.asyncio
class TestIncapacidadUploadSuccess:
    async def test_201_radicado_y_estado_procesando_ia(self, client: AsyncClient):
        token, uid = _token(UserRole.COLABORADOR)
        iid = uuid.uuid4()
        row = MagicMock(spec=Incapacidad)
        row.id = iid
        row.radicado = "IN0123456789ABCDEF0"
        row.estado = IncapacidadEstado.RECIBIDA
        row.archivo_path = "/tmp/test/doc.pdf"
        row.cargado_por = uid

        with (
            patch(
                "app.api.v1.routes.incapacidades.register_incapacidad_upload",
                new_callable=AsyncMock,
                return_value=row,
            ),
            patch(
                "app.api.v1.routes.incapacidades.run_incapacidad_extraction_job",
            ) as job,
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "doc.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 201
        body = response.json()
        assert body == {
            "radicado": "IN0123456789ABCDEF0",
            "estado": "procesando_ia",
        }
        job.assert_called_once_with(iid, "/tmp/test/doc.pdf", uid)

    async def test_colaborador_id_por_defecto_es_el_del_token(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        captured: dict = {}

        async def capture(*_args, **kwargs):
            captured["colaborador_id"] = kwargs["colaborador_id"]
            row = MagicMock(spec=Incapacidad)
            row.id = uuid.uuid4()
            row.radicado = "IN00000000000000001"
            row.estado = IncapacidadEstado.RECIBIDA
            row.archivo_path = "/x/a.pdf"
            row.cargado_por = uid
            return row

        with (
            patch(
                "app.api.v1.routes.incapacidades.register_incapacidad_upload",
                side_effect=capture,
            ),
            patch(
                "app.api.v1.routes.incapacidades.run_incapacidad_extraction_job",
            ),
        ):
            await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert captured["colaborador_id"] == uid


@pytest.mark.asyncio
class TestIncapacidadUploadAuthz:
    async def test_rechaza_peticion_sin_token(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/incapacidades/upload",
            files={
                "archivo": (
                    "a.pdf",
                    BytesIO(b"%PDF-1.4"),
                    "application/pdf",
                )
            },
        )
        # HTTPBearer de Starlette usa 403 cuando falta Authorization.
        assert response.status_code in (401, 403)

    async def test_403_colaborador_no_puede_cargar_para_otro(self, client: AsyncClient):
        token, _ = _token(UserRole.COLABORADOR)
        otro = uuid.uuid4()

        response = await client.post(
            "/api/v1/incapacidades/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"colaborador_id": str(otro)},
            files={
                "archivo": (
                    "a.pdf",
                    BytesIO(b"%PDF-1.4"),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 403

    async def test_201_rrhh_puede_indicar_otro_colaborador(self, client: AsyncClient):
        token, cargador = _token(UserRole.AUXILIAR_RRHH)
        colab = uuid.uuid4()
        row = MagicMock(spec=Incapacidad)
        row.id = uuid.uuid4()
        row.radicado = "INAAAAAAAAAAAAAAAA"
        row.estado = IncapacidadEstado.RECIBIDA
        row.archivo_path = "/x/b.pdf"
        row.cargado_por = cargador

        with (
            patch(
                "app.api.v1.routes.incapacidades.register_incapacidad_upload",
                new_callable=AsyncMock,
                return_value=row,
            ) as reg,
            patch(
                "app.api.v1.routes.incapacidades.run_incapacidad_extraction_job",
            ),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"colaborador_id": str(colab)},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 201
        reg.assert_awaited_once()
        call_kw = reg.await_args.kwargs
        assert call_kw["colaborador_id"] == colab

    async def test_201_recepcion_puede_indicar_otro_colaborador(
        self, client: AsyncClient
    ):
        token, cargador = _token(UserRole.RECEPCION)
        colab = uuid.uuid4()
        row = MagicMock(spec=Incapacidad)
        row.id = uuid.uuid4()
        row.radicado = "INBBBBBBBBBBBBBBBB"
        row.estado = IncapacidadEstado.RECIBIDA
        row.archivo_path = "/x/c.pdf"
        row.cargado_por = cargador

        with (
            patch(
                "app.api.v1.routes.incapacidades.register_incapacidad_upload",
                new_callable=AsyncMock,
                return_value=row,
            ) as reg,
            patch(
                "app.api.v1.routes.incapacidades.run_incapacidad_extraction_job",
            ),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                data={"colaborador_id": str(colab)},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 201
        reg.assert_awaited_once()
        assert reg.await_args.kwargs["colaborador_id"] == colab


@pytest.mark.asyncio
class TestIncapacidadUploadValidation:
    async def test_422_colaborador_id_invalido(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)

        response = await client.post(
            "/api/v1/incapacidades/upload",
            headers={"Authorization": f"Bearer {token}"},
            data={"colaborador_id": "no-es-uuid"},
            files={
                "archivo": (
                    "a.pdf",
                    BytesIO(b"%PDF-1.4"),
                    "application/pdf",
                )
            },
        )
        assert response.status_code == 422

    async def test_404_colaborador_inexistente_en_servicio(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)

        with patch(
            "app.api.v1.routes.incapacidades.register_incapacidad_upload",
            new_callable=AsyncMock,
            side_effect=ValueError("El colaborador indicado no existe."),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 404

    async def test_413_archivo_demasiado_grande(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        from app.services.incapacidad_storage import IncapacidadStorageError

        with patch(
            "app.api.v1.routes.incapacidades.register_incapacidad_upload",
            new_callable=AsyncMock,
            side_effect=IncapacidadStorageError(
                "El archivo supera el tamaño máximo permitido (10 bytes)."
            ),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 413

    async def test_400_error_de_tipo_de_archivo(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        from app.services.incapacidad_storage import IncapacidadStorageError

        with patch(
            "app.api.v1.routes.incapacidades.register_incapacidad_upload",
            new_callable=AsyncMock,
            side_effect=IncapacidadStorageError("Tipo de archivo no permitido."),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )

        assert response.status_code == 400

    async def test_500_runtime_error_radicado(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.incapacidades.register_incapacidad_upload",
            new_callable=AsyncMock,
            side_effect=RuntimeError("No se pudo generar un radicado único."),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 500

    async def test_500_error_escritura_disco(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.incapacidades.register_incapacidad_upload",
            new_callable=AsyncMock,
            side_effect=OSError(errno.EIO, "disk"),
        ):
            response = await client.post(
                "/api/v1/incapacidades/upload",
                headers={"Authorization": f"Bearer {token}"},
                files={
                    "archivo": (
                        "a.pdf",
                        BytesIO(b"%PDF-1.4"),
                        "application/pdf",
                    )
                },
            )
        assert response.status_code == 500
