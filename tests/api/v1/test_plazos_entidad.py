"""Tests CRUD /api/v1/admin/plazos-entidad (SCRUM-174)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.entidad_plazo import EntidadPlazo, UnidadPlazo
from app.models.user import UserRole


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(uid, role.value, f"{uid.hex}@test.local")


def _plazo_mock() -> EntidadPlazo:
    row = MagicMock(spec=EntidadPlazo)
    row.id = uuid.uuid4()
    row.entidad_nombre = "Salud Total"
    row.tipo_incapacidad = "accidente_transito"
    row.valor_limite = 15
    row.unidad_limite = UnidadPlazo.DIAS
    row.dias_limite = 15
    row.dias_alerta = 3
    now = datetime.now(UTC)
    row.created_at = now
    row.updated_at = now
    return row


@pytest.mark.asyncio
class TestPlazosEntidadAdmin:
    async def test_list_403_no_admin(self, client: AsyncClient) -> None:
        r = await client.get(
            "/api/v1/admin/plazos-entidad",
            headers={"Authorization": f"Bearer {_token(UserRole.COLABORADOR)}"},
        )
        assert r.status_code == 403

    async def test_list_200_admin(self, client: AsyncClient) -> None:
        row = _plazo_mock()
        with patch(
            "app.api.v1.routes.plazos_entidad.list_entidad_plazos",
            new_callable=AsyncMock,
            return_value=([row], 1),
        ):
            r = await client.get(
                "/api/v1/admin/plazos-entidad",
                headers={"Authorization": f"Bearer {_token(UserRole.ADMIN)}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["entidad_nombre"] == "Salud Total"
        assert body["items"][0]["dias_limite"] == 15

    async def test_create_201(self, client: AsyncClient) -> None:
        row = _plazo_mock()
        with patch(
            "app.api.v1.routes.plazos_entidad.create_entidad_plazo",
            new_callable=AsyncMock,
            return_value=row,
        ):
            r = await client.post(
                "/api/v1/admin/plazos-entidad",
                headers={"Authorization": f"Bearer {_token(UserRole.ADMIN)}"},
                json={
                    "entidad_nombre": "Salud Total",
                    "tipo_incapacidad": "accidente_transito",
                    "valor_limite": 15,
                    "unidad_limite": "dias",
                    "dias_alerta": 3,
                },
            )
        assert r.status_code == 201
        assert r.json()["dias_limite"] == 15

    async def test_delete_204(self, client: AsyncClient) -> None:
        pid = uuid.uuid4()
        row = _plazo_mock()
        row.id = pid
        with (
            patch(
                "app.api.v1.routes.plazos_entidad.get_entidad_plazo",
                new_callable=AsyncMock,
                return_value=row,
            ),
            patch(
                "app.api.v1.routes.plazos_entidad.delete_entidad_plazo",
                new_callable=AsyncMock,
            ),
        ):
            r = await client.delete(
                f"/api/v1/admin/plazos-entidad/{pid}",
                headers={"Authorization": f"Bearer {_token(UserRole.ADMIN)}"},
            )
        assert r.status_code == 204
