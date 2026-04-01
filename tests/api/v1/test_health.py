"""Tests del endpoint /api/v1/health."""

from unittest.mock import AsyncMock, MagicMock

from httpx import AsyncClient


class TestHealthCheck:
    async def test_returns_ok_status(self, client: AsyncClient):
        response = await client.get("/api/v1/health/")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"

    async def test_response_contains_message(self, client: AsyncClient):
        response = await client.get("/api/v1/health/")

        body = response.json()
        assert "message" in body


class TestHealthCheckDb:
    async def test_returns_ok_when_db_is_connected(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        response = await client.get("/api/v1/health/db")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] == "conectada"
        mock_db.execute.assert_called_once()

    async def test_uses_db_dependency(self, client: AsyncClient, mock_db: AsyncMock):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_db.execute.return_value = mock_result

        await client.get("/api/v1/health/db")

        mock_db.execute.assert_called_once()
