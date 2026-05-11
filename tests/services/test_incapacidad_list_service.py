"""Tests del servicio de listado paginado de incapacidades (SCRUM-130)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.incapacidad import IncapacidadEstado
from app.services.incapacidad_list_service import (
    IncapacidadListRow,
    list_incapacidades_paginated,
    total_pages,
)


@pytest.mark.parametrize(
    ("total", "page_size", "expected"),
    [
        (0, 20, 0),
        (5, 20, 1),
        (20, 20, 1),
        (21, 20, 2),
        (45, 20, 3),
        (10, 0, 0),
        (-1, 20, 0),
    ],
)
def test_total_pages(total: int, page_size: int, expected: int) -> None:
    assert total_pages(total, page_size) == expected


def _mock_db_results(*, total: int, list_rows: list) -> AsyncMock:
    db = AsyncMock()
    mock_count = MagicMock()
    mock_count.scalar_one.return_value = total
    mock_list = MagicMock()
    mock_list.all.return_value = list_rows
    db.execute = AsyncMock(side_effect=[mock_count, mock_list])
    return db


def _tuple_row(
    inc: MagicMock,
    nom: str | None = "Nombre Colab",
    eml: str | None = "c@test.local",
    en: str | None = None,
    et: str | None = None,
    nit: str | None = None,
    ec: str | None = None,
    tipo_ext: str | None = None,
) -> tuple:
    return (inc, nom, eml, en, et, nit, ec, tipo_ext)


@pytest.mark.asyncio
async def test_list_sin_filtros_ni_join() -> None:
    row_inc = MagicMock()
    db = _mock_db_results(total=3, list_rows=[_tuple_row(row_inc)])
    rows, total = await list_incapacidades_paginated(
        db,
        page=1,
        page_size=10,
        estado=None,
        tipo=None,
        entidad=None,
        colaborador_id_scope=None,
    )
    assert total == 3
    assert len(rows) == 1
    assert isinstance(rows[0], IncapacidadListRow)
    assert rows[0].incapacidad is row_inc
    assert rows[0].colaborador_nombre == "Nombre Colab"
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_con_estado_scope_y_tipo_archivo() -> None:
    db = _mock_db_results(total=1, list_rows=[])
    cid = uuid.uuid4()
    await list_incapacidades_paginated(
        db,
        page=1,
        page_size=5,
        estado=IncapacidadEstado.EN_VERIFICACION,
        tipo="  PNG ",
        entidad=None,
        colaborador_id_scope=cid,
    )
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_list_tipo_negocio_y_entidad_usa_join() -> None:
    db = _mock_db_results(total=0, list_rows=[])
    await list_incapacidades_paginated(
        db,
        page=2,
        page_size=2,
        estado=None,
        tipo="laboral",
        entidad="Sanitas",
        colaborador_id_scope=None,
    )
    assert db.execute.await_count == 2
