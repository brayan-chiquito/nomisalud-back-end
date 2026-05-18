"""Tests PATCH /api/v1/incapacidades/{id}/estado (SCRUM-137)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.services.incapacidad_estado_service import IncapacidadCambioEstadoError


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"user-{uid.hex[:8]}@test.local",
    )


@pytest.mark.asyncio
class TestIncapacidadPatchEstado:
    async def test_403_colaborador(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.COLABORADOR)
        r = await client.patch(
            f"/api/v1/incapacidades/{iid}/estado",
            headers={"Authorization": f"Bearer {token}"},
            json={"estado": "transcrita"},
        )
        assert r.status_code == 403

    async def test_200(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.ADMIN)
        inc = MagicMock(spec=Incapacidad)
        inc.id = iid
        inc.radicado = "IN0123456789ABCDEF0"
        inc.estado = IncapacidadEstado.TRANSCRITA

        with patch(
            "app.api.v1.routes.incapacidades.aplicar_parche_estado_incapacidad",
            new_callable=AsyncMock,
            return_value=(inc, IncapacidadEstado.EN_VERIFICACION),
        ):
            r = await client.patch(
                f"/api/v1/incapacidades/{iid}/estado",
                headers={"Authorization": f"Bearer {token}"},
                json={"estado": "transcrita", "observacion": "Listo"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "id": str(iid),
            "radicado": "IN0123456789ABCDEF0",
            "estado": "transcrita",
            "estado_anterior": "en_verificacion",
        }

    async def test_404_desde_servicio(self, client: AsyncClient):
        iid = uuid.uuid4()
        token = _token(UserRole.COORDINADOR_RRHH)
        with patch(
            "app.api.v1.routes.incapacidades.aplicar_parche_estado_incapacidad",
            new_callable=AsyncMock,
            side_effect=IncapacidadCambioEstadoError(404, "Incapacidad no encontrada."),
        ):
            r = await client.patch(
                f"/api/v1/incapacidades/{iid}/estado",
                headers={"Authorization": f"Bearer {token}"},
                json={"estado": "transcrita"},
            )
        assert r.status_code == 404
