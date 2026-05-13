"""Tests PUT /api/v1/incapacidades/{id}/verificar (SCRUM-134)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.services.incapacidad_verify_service import IncapacidadVerifyError


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"user-{uid.hex[:8]}@test.local",
    )


@pytest.mark.asyncio
class TestIncapacidadVerificarPut:
    async def test_403_colaborador(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.COLABORADOR)
        r = await client.put(
            f"/api/v1/incapacidades/{iid}/verificar",
            headers={"Authorization": f"Bearer {token}"},
            json={"accion": "confirmar"},
        )
        assert r.status_code == 403

    async def test_422_rechazar_sin_motivo(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.ADMIN)
        r = await client.put(
            f"/api/v1/incapacidades/{iid}/verificar",
            headers={"Authorization": f"Bearer {token}"},
            json={"accion": "rechazar"},
        )
        assert r.status_code == 422

    async def test_200_confirmar(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.COORDINADOR_RRHH)
        inc = MagicMock(spec=Incapacidad)
        inc.id = iid
        inc.radicado = "IN0123456789ABCDEF0"
        inc.estado = IncapacidadEstado.EN_VERIFICACION

        with patch(
            "app.api.v1.routes.incapacidades.verify_incapacidad_manual",
            new_callable=AsyncMock,
            return_value=inc,
        ) as fn:
            r = await client.put(
                f"/api/v1/incapacidades/{iid}/verificar",
                headers={"Authorization": f"Bearer {token}"},
                json={"accion": "confirmar"},
            )

        assert r.status_code == 200
        assert r.json() == {
            "id": str(iid),
            "radicado": "IN0123456789ABCDEF0",
            "estado": "en_verificacion",
        }
        fn.assert_awaited_once()

    async def test_200_rechazar(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.AUXILIAR_RRHH)
        inc = MagicMock(spec=Incapacidad)
        inc.id = iid
        inc.radicado = "IN09999999999999999"
        inc.estado = IncapacidadEstado.RECHAZADA

        with patch(
            "app.api.v1.routes.incapacidades.verify_incapacidad_manual",
            new_callable=AsyncMock,
            return_value=inc,
        ):
            r = await client.put(
                f"/api/v1/incapacidades/{iid}/verificar",
                headers={"Authorization": f"Bearer {token}"},
                json={"accion": "rechazar", "motivo_rechazo": "Documento ilegible"},
            )

        assert r.status_code == 200
        assert r.json()["estado"] == "rechazada"

    async def test_404_desde_servicio(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.incapacidades.verify_incapacidad_manual",
            new_callable=AsyncMock,
            side_effect=IncapacidadVerifyError(404, "Incapacidad no encontrada."),
        ):
            r = await client.put(
                f"/api/v1/incapacidades/{iid}/verificar",
                headers={"Authorization": f"Bearer {token}"},
                json={"accion": "confirmar"},
            )
        assert r.status_code == 404
