"""Tests del endpoint POST /api/v1/auth/login."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.user import UserRole


def _make_mock_user(
    *,
    email: str = "usuario@example.com",
    password_hash: str = "$2b$12$fakehash",
    role: UserRole = UserRole.COLABORADOR,
) -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = email
    user.password_hash = password_hash
    user.role = role
    return user


class TestLoginSuccess:
    async def test_returns_200_with_valid_credentials(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_user = _make_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=True):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "contraseña_correcta"},
            )

        assert response.status_code == 200

    async def test_response_contains_access_token(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_user = _make_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=True):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "contraseña_correcta"},
            )

        body = response.json()
        assert "access_token" in body
        assert isinstance(body["access_token"], str)
        assert len(body["access_token"]) > 0

    async def test_response_token_type_is_bearer(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_user = _make_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=True):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "contraseña_correcta"},
            )

        assert response.json()["token_type"] == "bearer"

    async def test_jwt_payload_contains_required_fields(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        """El JWT debe codificar estrictamente user_id, role y email."""
        from jose import jwt

        from app.core.config import get_settings

        mock_user = _make_mock_user(role=UserRole.ADMIN)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=True):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "contraseña_correcta"},
            )

        settings = get_settings()
        token = response.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        assert payload["user_id"] == str(mock_user.id)
        assert payload["role"] == mock_user.role.value
        assert payload["email"] == mock_user.email


class TestLoginFailure:
    async def test_returns_401_when_user_not_found(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "noexiste@example.com", "password": "cualquier_pass"},
        )

        assert response.status_code == 401

    async def test_returns_401_when_password_is_wrong(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_user = _make_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=False):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "contraseña_incorrecta"},
            )

        assert response.status_code == 401

    async def test_error_response_contains_detail(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "noexiste@example.com", "password": "pass"},
        )

        body = response.json()
        assert "detail" in body

    async def test_error_response_has_www_authenticate_header(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "noexiste@example.com", "password": "pass"},
        )

        assert response.headers.get("www-authenticate") == "Bearer"

    async def test_returns_401_not_403_on_invalid_credentials(
        self, client: AsyncClient, mock_db: AsyncMock
    ):
        """Debe retornar 401 (no 403) para no revelar si el usuario existe."""
        mock_user = _make_mock_user()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        with patch("app.api.v1.routes.auth.verify_password", return_value=False):
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": mock_user.email, "password": "pass_incorrecto"},
            )

        assert response.status_code == 401
        assert response.status_code != 403
