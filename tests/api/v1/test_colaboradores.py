"""Tests API búsqueda de colaboradores (SCRUM-197)."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import UserRole


def _token(role: UserRole) -> str:
    return create_access_token(
        user_id=uuid.uuid4(),
        role=role.value,
        email=f"{role.value}@test.local",
    )


@pytest.mark.asyncio
class TestColaboradoresBuscar:
    async def test_200_recepcion(self, client: AsyncClient):
        token = _token(UserRole.RECEPCION)
        colab = MagicMock()
        colab.id = uuid.uuid4()
        colab.nombre_completo = "Juan Pérez"
        colab.numero_documento = "1000000005"
        colab.email = "juan@test.local"

        with patch(
            "app.api.v1.routes.colaboradores.buscar_colaboradores",
            new_callable=AsyncMock,
            return_value=[colab],
        ):
            response = await client.get(
                "/api/v1/colaboradores/buscar?q=juan",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["nombre_completo"] == "Juan Pérez"

    async def test_403_colaborador(self, client: AsyncClient):
        token = _token(UserRole.COLABORADOR)
        response = await client.get(
            "/api/v1/colaboradores/buscar?q=ana",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
