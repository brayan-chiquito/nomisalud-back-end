"""Tests del registro de incapacidad (servicio)."""

import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.datastructures import UploadFile

from app.models.incapacidad import IncapacidadEstado
from app.services.incapacidad_upload_service import register_incapacidad_upload


@pytest.mark.asyncio
async def test_register_falla_si_colaborador_no_existe(tmp_path):
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    cid = uuid.uuid4()
    up = UploadFile(filename="a.pdf", file=BytesIO(b"%PDF-1.4"))

    with pytest.raises(ValueError, match="no existe"):
        await register_incapacidad_upload(
            mock_db,
            upload=up,
            colaborador_id=cid,
            cargado_por_id=cid,
            storage_dir=tmp_path,
            max_upload_bytes=4096,
        )


@pytest.mark.asyncio
async def test_register_persiste_y_construye_fila(tmp_path):
    cid = uuid.uuid4()

    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = MagicMock()
    mock_db.execute.return_value = mock_res

    @asynccontextmanager
    async def nested():
        yield

    mock_db.begin_nested = MagicMock(return_value=nested())
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    up = UploadFile(
        filename="c.pdf",
        file=BytesIO(b"%PDF-1.4 ok"),
        headers={"content-type": "application/pdf"},
    )

    row = await register_incapacidad_upload(
        mock_db,
        upload=up,
        colaborador_id=cid,
        cargado_por_id=cid,
        storage_dir=tmp_path,
        max_upload_bytes=4096,
    )

    assert row.colaborador_id == cid
    assert row.cargado_por == cid
    assert row.user_id == cid
    assert row.estado == IncapacidadEstado.RECIBIDA
    assert len(row.radicado) == 20
    assert row.radicado.startswith("IN")
    assert row.archivo_tipo.value == "pdf"
    mock_db.begin_nested.assert_called()
    mock_db.flush.assert_awaited()
    mock_db.refresh.assert_awaited_once()

    stored = list(tmp_path.glob(f"{row.archivo_uuid}.*"))
    assert len(stored) == 1
    assert isinstance(stored[0], Path)
    assert row.archivo_path == str(stored[0])
