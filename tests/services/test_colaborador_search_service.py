"""Tests de búsqueda de colaboradores."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.colaborador_search_service import buscar_colaboradores


@pytest.mark.asyncio
async def test_buscar_vacio_si_termino_blanco() -> None:
    db = AsyncMock()
    assert await buscar_colaboradores(db, termino="   ") == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_buscar_devuelve_filas() -> None:
    user = MagicMock()
    user.id = uuid.uuid4()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [user]
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)

    rows = await buscar_colaboradores(db, termino="juan", limit=5)
    assert rows == [user]
    db.execute.assert_awaited_once()
