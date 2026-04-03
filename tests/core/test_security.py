"""Tests unitarios para app/core/security.py."""

import pytest

from app.core.security import hash_password, verify_password


class TestHashPassword:
    def test_returns_string(self):
        result = hash_password("mi_contraseña_123")
        assert isinstance(result, str)

    def test_hash_is_not_plain_text(self):
        plain = "mi_contraseña_123"
        assert hash_password(plain) != plain

    def test_hash_starts_with_bcrypt_prefix(self):
        result = hash_password("cualquier_pass")
        assert result.startswith("$2b$")

    def test_two_hashes_of_same_password_are_different(self):
        """bcrypt usa sal aleatoria: dos hashes del mismo texto no deben ser iguales."""
        plain = "misma_contraseña"
        assert hash_password(plain) != hash_password(plain)


class TestVerifyPassword:
    def test_returns_true_for_correct_password(self):
        plain = "contraseña_correcta"
        hashed = hash_password(plain)
        assert verify_password(plain, hashed) is True

    def test_returns_false_for_wrong_password(self):
        hashed = hash_password("contraseña_original")
        assert verify_password("contraseña_incorrecta", hashed) is False

    def test_returns_false_for_empty_string(self):
        hashed = hash_password("alguna_contraseña")
        assert verify_password("", hashed) is False

    def test_is_case_sensitive(self):
        plain = "ContraseñaConMayusculas"
        hashed = hash_password(plain)
        assert verify_password("contraseñaconmayusculas", hashed) is False
