"""
Configuración global de pytest.

El conftest raíz sobreescribe la dependencia de base de datos para que
los tests de la capa HTTP corran sin necesitar una instancia real de PostgreSQL.
"""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app


@pytest.fixture
def mock_db() -> AsyncMock:
    """Sesión de base de datos simulada."""
    session = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def override_db_dependency(mock_db: AsyncMock):
    """
    Reemplaza get_db en toda la suite para evitar conexiones reales.
    Se restaura automáticamente después de cada test.
    """
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def client() -> AsyncClient:
    """Cliente HTTP asíncrono apuntando a la app ASGI en memoria."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
