"""Tests del servicio de verificación manual (SCRUM-134)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.historial_estado import HistorialEstado
from app.models.incapacidad import IncapacidadEstado
from app.services.incapacidad_verify_service import (
    IncapacidadVerifyError,
    verify_incapacidad_manual,
)


def _setup_session(inc: MagicMock) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = inc
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_confirmar_sin_datos_mantiene_json_y_estado_en_verificacion() -> None:
    iid = uuid.uuid4()
    actor = uuid.uuid4()
    ext = MagicMock()
    ext.datos_extraidos = {"a": 1}

    inc = MagicMock()
    inc.id = iid
    inc.estado = IncapacidadEstado.DOC_INCOMPLETA
    inc.extraccion_ia = ext

    db = _setup_session(inc)
    out = await verify_incapacidad_manual(
        db,
        incapacidad_id=iid,
        actor_id=actor,
        accion="confirmar",
        motivo_rechazo=None,
        datos_extraidos=None,
    )
    assert out.estado == IncapacidadEstado.EN_VERIFICACION
    assert ext.datos_extraidos == {"a": 1}
    assert ext.verificado_por == actor
    assert ext.verificado_en is not None
    db.add.assert_called_once()
    hist = db.add.call_args[0][0]
    assert isinstance(hist, HistorialEstado)
    assert hist.estado_nuevo == IncapacidadEstado.EN_VERIFICACION
    assert hist.estado_anterior == IncapacidadEstado.DOC_INCOMPLETA


@pytest.mark.asyncio
async def test_confirmar_en_verificacion_sin_historial_duplicado() -> None:
    iid = uuid.uuid4()
    ext = MagicMock()
    inc = MagicMock()
    inc.id = iid
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.extraccion_ia = ext
    db = _setup_session(inc)

    await verify_incapacidad_manual(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        accion="confirmar",
        motivo_rechazo=None,
        datos_extraidos=None,
    )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_confirmar_desde_transcrita_409() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.estado = IncapacidadEstado.TRANSCRITA
    inc.extraccion_ia = ext
    db = _setup_session(inc)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="confirmar",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_confirmar_reemplaza_datos_extraidos() -> None:
    iid = uuid.uuid4()
    ext = MagicMock()
    ext.datos_extraidos = {"old": True}
    inc = MagicMock()
    inc.id = iid
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.extraccion_ia = ext
    db = _setup_session(inc)

    await verify_incapacidad_manual(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        accion="confirmar",
        motivo_rechazo=None,
        datos_extraidos={"paciente": {"nombre_completo": "X"}},
    )
    assert ext.datos_extraidos["paciente"]["nombre_completo"] == "X"
    assert ext.datos_extraidos["colaborador"]["nombre_completo"] == "X"
    assert "incapacidad" in ext.datos_extraidos


@pytest.mark.asyncio
async def test_rechazar_guarda_motivo_y_estado() -> None:
    iid = uuid.uuid4()
    ext = MagicMock()
    inc = MagicMock()
    inc.id = iid
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.documentacion_faltante = None
    inc.extraccion_ia = ext
    db = _setup_session(inc)

    await verify_incapacidad_manual(
        db,
        incapacidad_id=iid,
        actor_id=uuid.uuid4(),
        accion="rechazar",
        motivo_rechazo="  No cumple política  ",
        datos_extraidos=None,
    )
    assert inc.estado == IncapacidadEstado.RECHAZADA
    assert inc.documentacion_faltante == ["No cumple política"]


@pytest.mark.asyncio
async def test_sin_incapacidad_404() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            accion="confirmar",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 404


@pytest.mark.asyncio
async def test_sin_extraccion_422() -> None:
    inc = MagicMock()
    inc.extraccion_ia = None
    db = _setup_session(inc)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="confirmar",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_accion_invalida_422() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.extraccion_ia = ext
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    db = _setup_session(inc)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="otro",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_rechazar_motivo_vacio_422() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.extraccion_ia = ext
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    db = _setup_session(inc)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="rechazar",
            motivo_rechazo="   ",
            datos_extraidos=None,
        )
    assert ei.value.status_code == 422


@pytest.mark.asyncio
async def test_estado_terminal_409() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.extraccion_ia = ext
    inc.estado = IncapacidadEstado.RECHAZADA
    db = _setup_session(inc)

    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            db,
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="confirmar",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 409
