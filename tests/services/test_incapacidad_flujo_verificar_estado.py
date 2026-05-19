"""Matriz de coherencia entre PUT verificar y PATCH estado."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.incapacidad import IncapacidadEstado
from app.services.incapacidad_estado_service import (
    IncapacidadCambioEstadoError,
    aplicar_parche_estado_incapacidad,
)
from app.services.incapacidad_transiciones import destinos_patch_validos
from app.services.incapacidad_verify_service import (
    IncapacidadVerifyError,
    verify_incapacidad_manual,
)


def _verify_session(inc: MagicMock) -> AsyncMock:
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = inc
    db.execute = AsyncMock(return_value=result)
    db.flush = AsyncMock()
    db.add = MagicMock()
    return db


def _patch_session(inc: MagicMock) -> AsyncMock:
    db = AsyncMock()
    db.get = AsyncMock(return_value=inc)
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        (IncapacidadEstado.EN_VERIFICACION, IncapacidadEstado.TRANSCRITA),
        (IncapacidadEstado.EN_VERIFICACION, IncapacidadEstado.DOC_INCOMPLETA),
        (IncapacidadEstado.EN_VERIFICACION, IncapacidadEstado.RECHAZADA),
        (IncapacidadEstado.DOC_INCOMPLETA, IncapacidadEstado.EN_VERIFICACION),
        (IncapacidadEstado.TRANSCRITA, IncapacidadEstado.COBRADA),
        (IncapacidadEstado.COBRADA, IncapacidadEstado.PAGADA),
        (
            IncapacidadEstado.INCONSISTENCIA_DETECTADA,
            IncapacidadEstado.EN_VERIFICACION,
        ),
    ],
)
@pytest.mark.asyncio
async def test_patch_transiciones_permitidas(
    origen: IncapacidadEstado,
    destino: IncapacidadEstado,
) -> None:
    assert destino in destinos_patch_validos(origen)
    inc = MagicMock()
    inc.estado = origen
    db = _patch_session(inc)
    obs = "motivo" if destino == IncapacidadEstado.RECHAZADA else None
    _, prev = await aplicar_parche_estado_incapacidad(
        db,
        incapacidad_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        nuevo_estado=destino,
        observacion=obs,
    )
    assert prev == origen
    assert inc.estado == destino


@pytest.mark.asyncio
async def test_flujo_confirmar_luego_transcribir() -> None:
    """Aceptar datos IA (confirmar) y luego aprobar trámite (PATCH transcrita)."""
    ext = MagicMock()
    inc = MagicMock()
    inc.id = uuid.uuid4()
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.extraccion_ia = ext

    db_v = _verify_session(inc)
    await verify_incapacidad_manual(
        db_v,
        incapacidad_id=inc.id,
        actor_id=uuid.uuid4(),
        accion="confirmar",
        motivo_rechazo=None,
        datos_extraidos=None,
    )
    assert inc.estado == IncapacidadEstado.EN_VERIFICACION
    db_v.add.assert_not_called()

    db_p = _patch_session(inc)
    _, prev = await aplicar_parche_estado_incapacidad(
        db_p,
        incapacidad_id=inc.id,
        actor_id=uuid.uuid4(),
        nuevo_estado=IncapacidadEstado.TRANSCRITA,
        observacion="Aprobado para cobro",
    )
    assert prev == IncapacidadEstado.EN_VERIFICACION
    assert inc.estado == IncapacidadEstado.TRANSCRITA


@pytest.mark.asyncio
async def test_rechazar_verificar_equivalente_patch_rechazada() -> None:
    """rechazar y PATCH→rechazada dejan el trámite en rechazada con motivo."""
    ext = MagicMock()
    inc_v = MagicMock()
    inc_v.id = uuid.uuid4()
    inc_v.estado = IncapacidadEstado.EN_VERIFICACION
    inc_v.extraccion_ia = ext
    await verify_incapacidad_manual(
        _verify_session(inc_v),
        incapacidad_id=inc_v.id,
        actor_id=uuid.uuid4(),
        accion="rechazar",
        motivo_rechazo="Motivo A",
        datos_extraidos=None,
    )
    assert inc_v.estado == IncapacidadEstado.RECHAZADA
    assert inc_v.documentacion_faltante == ["Motivo A"]

    inc_p = MagicMock()
    inc_p.estado = IncapacidadEstado.EN_VERIFICACION
    await aplicar_parche_estado_incapacidad(
        _patch_session(inc_p),
        incapacidad_id=uuid.uuid4(),
        actor_id=uuid.uuid4(),
        nuevo_estado=IncapacidadEstado.RECHAZADA,
        observacion="Motivo B",
    )
    assert inc_p.estado == IncapacidadEstado.RECHAZADA
    assert inc_p.documentacion_faltante == ["Motivo B"]


@pytest.mark.asyncio
async def test_patch_transcrita_no_permitido_tras_rechazar() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.estado = IncapacidadEstado.EN_VERIFICACION
    inc.extraccion_ia = ext
    await verify_incapacidad_manual(
        _verify_session(inc),
        incapacidad_id=inc.id,
        actor_id=uuid.uuid4(),
        accion="rechazar",
        motivo_rechazo="X",
        datos_extraidos=None,
    )
    with pytest.raises(IncapacidadCambioEstadoError) as ei:
        await aplicar_parche_estado_incapacidad(
            _patch_session(inc),
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            nuevo_estado=IncapacidadEstado.TRANSCRITA,
            observacion=None,
        )
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_verificar_tras_rechazar_409() -> None:
    ext = MagicMock()
    inc = MagicMock()
    inc.estado = IncapacidadEstado.RECHAZADA
    inc.extraccion_ia = ext
    with pytest.raises(IncapacidadVerifyError) as ei:
        await verify_incapacidad_manual(
            _verify_session(inc),
            incapacidad_id=inc.id,
            actor_id=uuid.uuid4(),
            accion="confirmar",
            motivo_rechazo=None,
            datos_extraidos=None,
        )
    assert ei.value.status_code == 409
