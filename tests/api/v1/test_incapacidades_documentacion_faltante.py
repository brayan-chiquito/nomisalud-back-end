"""Tests PUT /api/v1/incapacidades/{id}/documentacion-faltante (SCRUM-144)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.services.incapacidad_documentacion_service import IncapacidadDocumentacionError


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"user-{uid.hex[:8]}@test.local",
    )


@pytest.mark.asyncio
class TestIncapacidadDocumentacionFaltante:
    async def test_403_colaborador(self, client: AsyncClient) -> None:
        iid = uuid.uuid4()
        r = await client.put(
            f"/api/v1/incapacidades/{iid}/documentacion-faltante",
            headers={"Authorization": f"Bearer {_token(UserRole.COLABORADOR)}"},
            json={"documentos": ["Certificado médico"]},
        )
        assert r.status_code == 403

    async def test_200(self, client: AsyncClient) -> None:
        iid = uuid.uuid4()
        inc = MagicMock(spec=Incapacidad)
        inc.id = iid
        inc.radicado = "IN0123456789ABCDEF0"
        inc.estado = IncapacidadEstado.DOC_INCOMPLETA
        inc.documentacion_faltante = ["Certificado médico", "Historia clínica"]

        with patch(
            "app.api.v1.routes.incapacidades.registrar_documentacion_faltante",
            new_callable=AsyncMock,
            return_value=(inc, IncapacidadEstado.EN_VERIFICACION),
        ):
            r = await client.put(
                f"/api/v1/incapacidades/{iid}/documentacion-faltante",
                headers={"Authorization": f"Bearer {_token(UserRole.ADMIN)}"},
                json={
                    "documentos": ["Certificado médico", "Historia clínica"],
                    "observacion": "Falta soporte",
                },
            )
        assert r.status_code == 200
        assert r.json() == {
            "id": str(iid),
            "radicado": "IN0123456789ABCDEF0",
            "estado": "doc_incompleta",
            "estado_anterior": "en_verificacion",
            "documentacion_faltante": ["Certificado médico", "Historia clínica"],
        }

    async def test_422_body_vacio(self, client: AsyncClient) -> None:
        iid = uuid.uuid4()
        r = await client.put(
            f"/api/v1/incapacidades/{iid}/documentacion-faltante",
            headers={"Authorization": f"Bearer {_token(UserRole.ADMIN)}"},
            json={"documentos": ["  "]},
        )
        assert r.status_code == 422

    async def test_404_desde_servicio(self, client: AsyncClient) -> None:
        iid = uuid.uuid4()
        with patch(
            "app.api.v1.routes.incapacidades.registrar_documentacion_faltante",
            new_callable=AsyncMock,
            side_effect=IncapacidadDocumentacionError(
                404,
                "Incapacidad no encontrada.",
            ),
        ):
            r = await client.put(
                f"/api/v1/incapacidades/{iid}/documentacion-faltante",
                headers={"Authorization": f"Bearer {_token(UserRole.AUXILIAR_RRHH)}"},
                json={"documentos": ["Doc"]},
            )
        assert r.status_code == 404
