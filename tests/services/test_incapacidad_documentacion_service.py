"""Tests del servicio de documentación faltante (SCRUM-144)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.services.incapacidad_documentacion_service import (
    IncapacidadDocumentacionError,
    registrar_documentacion_faltante,
)


@pytest.mark.asyncio
async def test_registro_desde_en_verificacion() -> None:
    iid = uuid.uuid4()
    inc = MagicMock(spec=Incapacidad)
    inc.id = iid
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.documentacion_faltante = None

    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()

    out, prev = await registrar_documentacion_faltante(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        documentos=["  Certificado médico ", "Historia clínica"],
    )
    assert out is inc
    assert prev == IncapacidadEstado.EN_VERIFICACION
    assert inc.estado == IncapacidadEstado.DOC_INCOMPLETA
    assert inc.documentacion_faltante == ["Certificado médico", "Historia clínica"]
    db.add.assert_called_once()
    assert isinstance(db.add.call_args[0][0], HistorialEstado)


@pytest.mark.asyncio
async def test_registro_desde_inconsistencia_detectada() -> None:
    inc = MagicMock(spec=Incapacidad)
    inc.id = uuid.uuid4()
    inc.estado = IncapacidadEstado.INCONSISTENCIA_DETECTADA
    inc.documentacion_faltante = None

    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()

    _, prev = await registrar_documentacion_faltante(
        db,
        incapacidad_id=inc.id,
        actor_id=uuid.uuid4(),
        documentos=["Epicrisis"],
    )
    assert prev == IncapacidadEstado.INCONSISTENCIA_DETECTADA
    assert inc.estado == IncapacidadEstado.DOC_INCOMPLETA


@pytest.mark.asyncio
async def test_actualiza_lista_si_ya_doc_incompleta() -> None:
    inc = MagicMock()
    inc.estado = IncapacidadEstado.DOC_INCOMPLETA
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()

    _, prev = await registrar_documentacion_faltante(
        db,
        incapacidad_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        documentos=["Nuevo documento"],
    )
    assert prev == IncapacidadEstado.DOC_INCOMPLETA
    assert inc.documentacion_faltante == ["Nuevo documento"]
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_404_no_existe() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    with pytest.raises(IncapacidadDocumentacionError) as ei:
        await registrar_documentacion_faltante(
            db,
            incapacidad_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            documentos=["Doc"],
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_422_lista_vacia() -> None:
    inc = MagicMock()
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    with pytest.raises(IncapacidadDocumentacionError) as ei:
        await registrar_documentacion_faltante(
            db,
            incapacidad_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            documentos=["  ", ""],
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_409_estado_no_admitido() -> None:
    inc = MagicMock()
    inc.estado = IncapacidadEstado.TRANSCRITA
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    with pytest.raises(IncapacidadDocumentacionError) as ei:
        await registrar_documentacion_faltante(
            db,
            incapacidad_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            documentos=["Doc"],
        )
    assert ei.value.status_code == 409
