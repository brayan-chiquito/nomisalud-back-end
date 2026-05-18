"""Tests del servicio de cambio de estado (SCRUM-137)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import Incapacidad, IncapacidadEstado
from app.services.incapacidad_estado_service import (
    IncapacidadCambioEstadoError,
    aplicar_parche_estado_incapacidad,
)


@pytest.mark.asyncio
async def test_transicion_en_verificacion_a_transcrita() -> None:
    iid = uuid.uuid4()
    inc = MagicMock(spec=Incapacidad)
    inc.id = iid
    inc.radicado = "IN01"
    inc.estado = IncapacidadEstado.EN_VERIFICACION

    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()

    out, prev = await aplicar_parche_estado_incapacidad(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        nuevo_estado=IncapacidadEstado.TRANSCRITA,
        observacion="OK",
    )
    assert out is inc
    assert prev == IncapacidadEstado.EN_VERIFICACION
    assert inc.estado == IncapacidadEstado.TRANSCRITA
    db.add.assert_called_once()
    hist = db.add.call_args[0][0]
    assert isinstance(hist, HistorialEstado)
    assert hist.estado_nuevo == IncapacidadEstado.TRANSCRITA
    assert hist.observacion == "OK"


@pytest.mark.asyncio
async def test_observacion_por_defecto() -> None:
    iid = uuid.uuid4()
    inc = MagicMock(spec=Incapacidad)
    inc.id = iid
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()

    await aplicar_parche_estado_incapacidad(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        nuevo_estado=IncapacidadEstado.DOC_INCOMPLETA,
        observacion=None,
    )
    hist = db.add.call_args[0][0]
    assert hist.observacion == "Cambio de estado: en_verificacion → doc_incompleta."


@pytest.mark.asyncio
async def test_mismo_estado_400() -> None:
    inc = MagicMock()
    inc.estado = IncapacidadEstado.TRANSCRITA
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)

    with pytest.raises(IncapacidadCambioEstadoError) as ei:
        await aplicar_parche_estado_incapacidad(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            nuevo_estado=IncapacidadEstado.TRANSCRITA,
            observacion=None,
        )
    assert ei.value.status_code == 400


@pytest.mark.asyncio
async def test_transicion_invalida_409() -> None:
    inc = MagicMock()
    inc.estado = IncapacidadEstado.RECIBIDA
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)

    with pytest.raises(IncapacidadCambioEstadoError) as ei:
        await aplicar_parche_estado_incapacidad(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            nuevo_estado=IncapacidadEstado.PAGADA,
            observacion=None,
        )
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_no_existe_404() -> None:
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    with pytest.raises(IncapacidadCambioEstadoError) as ei:
        await aplicar_parche_estado_incapacidad(
            db,
            incapacidad_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            nuevo_estado=IncapacidadEstado.TRANSCRITA,
            observacion=None,
        )
    assert ei.value.status_code == 404
