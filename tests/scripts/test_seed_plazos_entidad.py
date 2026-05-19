"""Seed de plazos reglamentarios."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.seed_plazos_entidad import SEED_PLAZOS, seed_plazos_entidad


@pytest.mark.asyncio
async def test_seed_plazos_inserta_si_no_existe() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("scripts.seed_plazos_entidad.AsyncSessionLocal", return_value=cm):
        await seed_plazos_entidad()

    assert session.add.call_count == len(SEED_PLAZOS)
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_seed_plazos_omite_existentes() -> None:
    session = AsyncMock()
    session.scalar = AsyncMock(return_value="ya-hay-id")
    session.add = MagicMock()
    session.commit = AsyncMock()

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("scripts.seed_plazos_entidad.AsyncSessionLocal", return_value=cm):
        await seed_plazos_entidad()

    session.add.assert_not_called()
