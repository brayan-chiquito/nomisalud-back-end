"""Tests unitarios para app/models/user.py."""

import uuid

import pytest

from app.models.user import User, UserRole


class TestUserRole:
    def test_has_four_roles(self):
        assert len(UserRole) == 4

    def test_colaborador_value(self):
        assert UserRole.COLABORADOR == "colaborador"

    def test_auxiliar_rrhh_value(self):
        assert UserRole.AUXILIAR_RRHH == "auxiliar_rrhh"

    def test_coordinador_rrhh_value(self):
        assert UserRole.COORDINADOR_RRHH == "coordinador_rrhh"

    def test_admin_value(self):
        assert UserRole.ADMIN == "admin"

    def test_is_str_subclass(self):
        """UserRole hereda str para ser directamente serializable como JSON."""
        for role in UserRole:
            assert isinstance(role, str)

    def test_all_expected_roles_exist(self):
        expected = {"colaborador", "auxiliar_rrhh", "coordinador_rrhh", "admin"}
        actual = {role.value for role in UserRole}
        assert actual == expected


class TestUserModel:
    def test_tablename(self):
        assert User.__tablename__ == "users"

    def test_repr_contains_email(self):
        user = User(
            id=uuid.uuid4(),
            email="test@nomisalud.com",
            password_hash="hashed",
            role=UserRole.ADMIN,
        )
        assert "test@nomisalud.com" in repr(user)

    def test_repr_contains_role(self):
        user = User(
            id=uuid.uuid4(),
            email="test@nomisalud.com",
            password_hash="hashed",
            role=UserRole.COLABORADOR,
        )
        assert "COLABORADOR" in repr(user)

    def test_repr_contains_id(self):
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            email="test@nomisalud.com",
            password_hash="hashed",
            role=UserRole.AUXILIAR_RRHH,
        )
        assert str(user_id) in repr(user)
