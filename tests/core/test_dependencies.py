"""Tests unitarios para app/core/dependencies.py."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import ExpiredSignatureError, JWTError

from app.core.dependencies import get_current_user, require_roles
from app.models.user import UserRole
from app.schemas.token import TokenPayload


def _make_credentials(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _make_payload(role: UserRole = UserRole.COLABORADOR) -> TokenPayload:
    return TokenPayload(
        user_id=str(uuid.uuid4()),
        role=role.value,
        email="test@example.com",
    )


class TestGetCurrentUser:
    def test_returns_token_payload_for_valid_token(self):
        payload_data = {
            "user_id": str(uuid.uuid4()),
            "role": UserRole.ADMIN.value,
            "email": "admin@example.com",
        }
        with patch(
            "app.core.dependencies.decode_access_token", return_value=payload_data
        ):
            result = get_current_user(_make_credentials("valid.token.here"))

        assert result.user_id == payload_data["user_id"]
        assert result.role == payload_data["role"]
        assert result.email == payload_data["email"]

    def test_raises_401_when_token_is_expired(self):
        with patch(
            "app.core.dependencies.decode_access_token",
            side_effect=ExpiredSignatureError(),
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(_make_credentials("expired.token"))

        assert exc_info.value.status_code == 401

    def test_raises_401_when_token_has_invalid_signature(self):
        with patch(
            "app.core.dependencies.decode_access_token",
            side_effect=JWTError(),
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(_make_credentials("tampered.token"))

        assert exc_info.value.status_code == 401

    def test_expired_error_message_is_descriptive(self):
        with patch(
            "app.core.dependencies.decode_access_token",
            side_effect=ExpiredSignatureError(),
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(_make_credentials("expired.token"))

        assert "expirado" in exc_info.value.detail.lower()

    def test_401_response_has_www_authenticate_header(self):
        with patch(
            "app.core.dependencies.decode_access_token",
            side_effect=JWTError(),
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_current_user(_make_credentials("bad.token"))

        assert exc_info.value.headers["WWW-Authenticate"] == "Bearer"


class TestRequireRoles:
    def test_passes_when_role_matches(self):
        payload = _make_payload(role=UserRole.ADMIN)
        checker = require_roles(UserRole.ADMIN)
        result = checker(current_user=payload)

        assert result == payload

    def test_raises_403_when_role_insufficient(self):
        payload = _make_payload(role=UserRole.COLABORADOR)
        checker = require_roles(UserRole.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=payload)

        assert exc_info.value.status_code == 403

    def test_passes_when_role_is_one_of_multiple_allowed(self):
        payload = _make_payload(role=UserRole.AUXILIAR_RRHH)
        checker = require_roles(UserRole.ADMIN, UserRole.AUXILIAR_RRHH)
        result = checker(current_user=payload)

        assert result == payload

    def test_raises_403_when_role_not_in_multiple_allowed(self):
        payload = _make_payload(role=UserRole.COLABORADOR)
        checker = require_roles(UserRole.ADMIN, UserRole.COORDINADOR_RRHH)

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=payload)

        assert exc_info.value.status_code == 403

    def test_403_detail_is_descriptive(self):
        payload = _make_payload(role=UserRole.COLABORADOR)
        checker = require_roles(UserRole.ADMIN)

        with pytest.raises(HTTPException) as exc_info:
            checker(current_user=payload)

        assert "insuficientes" in exc_info.value.detail.lower()

    def test_returns_current_user_on_success(self):
        payload = _make_payload(role=UserRole.COORDINADOR_RRHH)
        checker = require_roles(UserRole.COORDINADOR_RRHH)
        result = checker(current_user=payload)

        assert result.role == UserRole.COORDINADOR_RRHH.value
        assert result.email == payload.email
