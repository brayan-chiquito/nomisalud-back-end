"""Tests del servicio de detalle de incapacidad (SCRUM-133)."""

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.incapacidad_detail_service import (
    get_incapacidad_detalle,
    resolve_archivo_under_storage,
)


@pytest.mark.asyncio
async def test_get_incapacidad_detalle_none() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    out = await get_incapacidad_detalle(db, uuid.uuid4())
    assert out is None


@pytest.mark.asyncio
async def test_get_incapacidad_detalle_ok() -> None:
    iid = uuid.uuid4()
    inc = MagicMock()
    ext = MagicMock()
    result = MagicMock()
    result.one_or_none.return_value = (inc, ext, "Nombre", "n@test")
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)

    out = await get_incapacidad_detalle(db, iid)
    assert out is not None
    assert out.incapacidad is inc
    assert out.extraccion_ia is ext
    assert out.colaborador_nombre == "Nombre"
    assert out.colaborador_email == "n@test"


def test_resolve_archivo_fuera_de_storage(tmp_path: Path) -> None:
    base = tmp_path / "up"
    base.mkdir()
    outside = tmp_path / "evil.pdf"
    outside.write_bytes(b"x")
    assert resolve_archivo_under_storage(str(outside), base) is None


def test_resolve_archivo_ok(tmp_path: Path) -> None:
    base = tmp_path / "up"
    base.mkdir()
    f = base / "a.pdf"
    f.write_bytes(b"x")
    got = resolve_archivo_under_storage(str(f), base)
    assert got == f.resolve()


def test_resolve_archivo_path_vacio(tmp_path: Path) -> None:
    base = tmp_path / "up"
    base.mkdir()
    assert resolve_archivo_under_storage(None, base) is None
    assert resolve_archivo_under_storage("", base) is None


def test_resolve_archivo_no_existe(tmp_path: Path) -> None:
    base = tmp_path / "up"
    base.mkdir()
    missing = base / "gone.pdf"
    assert resolve_archivo_under_storage(str(missing), base) is None
