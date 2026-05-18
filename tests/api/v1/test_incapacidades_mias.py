"""Tests del endpoint GET /api/v1/incapacidades/mias (SCRUM-141)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.models.user import UserRole


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


@pytest.mark.asyncio
class TestIncapacidadesMiasGet:
    async def test_200_estado_y_updated_at(self, client: AsyncClient) -> None:
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        iid = uuid.uuid4()
        updated = datetime(2025, 4, 10, 15, 30, tzinfo=UTC)
        inc = MagicMock(spec=Incapacidad)
        inc.id = iid
        inc.radicado = "IN0123456789ABCDEF0"
        inc.estado = IncapacidadEstado.EN_VERIFICACION
        inc.updated_at = updated

        with patch(
            "app.api.v1.routes.incapacidades.list_mis_incapacidades_paginated",
            new_callable=AsyncMock,
            return_value=([inc], 1),
        ) as list_mock:
            response = await client.get(
                "/api/v1/incapacidades/mias?page=1",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["pages"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0] == {
            "id": str(iid),
            "radicado": "IN0123456789ABCDEF0",
            "estado": "en_verificacion",
            "updated_at": updated.isoformat().replace("+00:00", "Z"),
        }
        list_mock.assert_awaited_once()
        assert list_mock.await_args.kwargs["colaborador_id"] == uid

    async def test_403_rrhh_no_colaborador(self, client: AsyncClient) -> None:
        token, _ = _token(UserRole.COORDINADOR_RRHH, uuid.uuid4())
        with patch(
            "app.api.v1.routes.incapacidades.list_mis_incapacidades_paginated",
            new_callable=AsyncMock,
        ) as list_mock:
            response = await client.get(
                "/api/v1/incapacidades/mias",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        list_mock.assert_not_called()

    async def test_401_sin_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/incapacidades/mias")
        assert response.status_code == 403
