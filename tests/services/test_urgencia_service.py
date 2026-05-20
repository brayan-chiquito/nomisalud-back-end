"""Tests del cálculo de urgencia (SCRUM-176)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.entidad_plazo import EntidadPlazo
from app.services.urgencia_service import (
    NivelUrgencia,
    buscar_plazo_entidad,
    calcular_dias_restantes,
    calcular_urgencia,
    cargar_indice_plazos,
    clasificar_urgencia_desde_plazo,
    parse_nivel_urgencia,
    resolver_plazo_en_indice,
    urgencia_desde_indice,
)


def test_calcular_dias_restantes() -> None:
    recepcion = datetime(2025, 1, 1, tzinfo=UTC)
    evaluacion = datetime(2025, 1, 10, tzinfo=UTC)
    assert (
        calcular_dias_restantes(
            fecha_recepcion=recepcion,
            dias_limite=15,
            fecha_evaluacion=evaluacion,
        )
        == 6
    )


def test_clasificar_verde_con_margen() -> None:
    recepcion = datetime(2025, 1, 1, tzinfo=UTC)
    evaluacion = datetime(2025, 1, 5, tzinfo=UTC)
    assert (
        clasificar_urgencia_desde_plazo(
            fecha_recepcion=recepcion,
            dias_limite=15,
            dias_alerta=3,
            fecha_evaluacion=evaluacion,
        )
        == NivelUrgencia.VERDE.value
    )


def test_clasificar_amarillo_en_ventana_alerta() -> None:
    recepcion = datetime(2025, 1, 1, tzinfo=UTC)
    evaluacion = datetime(2025, 1, 13, tzinfo=UTC)
    assert (
        clasificar_urgencia_desde_plazo(
            fecha_recepcion=recepcion,
            dias_limite=15,
            dias_alerta=3,
            fecha_evaluacion=evaluacion,
        )
        == NivelUrgencia.AMARILLO.value
    )


def test_clasificar_rojo_vencido() -> None:
    recepcion = datetime(2025, 1, 1, tzinfo=UTC)
    evaluacion = datetime(2025, 1, 20, tzinfo=UTC)
    assert (
        clasificar_urgencia_desde_plazo(
            fecha_recepcion=recepcion,
            dias_limite=15,
            dias_alerta=3,
            fecha_evaluacion=evaluacion,
        )
        == NivelUrgencia.ROJO.value
    )


def test_parse_nivel_urgencia_valido() -> None:
    assert parse_nivel_urgencia("  AMARILLO ") == "amarillo"
    assert parse_nivel_urgencia(None) is None


def test_parse_nivel_urgencia_invalido() -> None:
    with pytest.raises(ValueError, match="urgencia no es válido"):
        parse_nivel_urgencia("azul")


def test_resolver_plazo_fallback_general() -> None:
    plazo_general = MagicMock(spec=EntidadPlazo)
    plazo_general.dias_limite = 10
    plazo_general.dias_alerta = 2
    indice = {("sura eps", "general"): plazo_general}
    assert (
        resolver_plazo_en_indice(
            indice,
            entidad_nombre="SURA EPS",
            tipo_incapacidad="laboral",
        )
        is plazo_general
    )


def test_urgencia_desde_indice_sin_plazo_es_verde() -> None:
    recepcion = datetime(2025, 3, 1, tzinfo=UTC)
    assert (
        urgencia_desde_indice(
            {},
            fecha_recepcion=recepcion,
            entidad_nombre="Desconocida",
            tipo_incapacidad="general",
        )
        == NivelUrgencia.VERDE.value
    )


@pytest.mark.asyncio
async def test_buscar_plazo_entidad() -> None:
    plazo = MagicMock(spec=EntidadPlazo)
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=plazo)
    encontrado = await buscar_plazo_entidad(
        db,
        entidad_nombre="Salud Total",
        tipo_incapacidad="general",
    )
    assert encontrado is plazo
    assert db.scalar.await_count == 1


@pytest.mark.asyncio
async def test_calcular_urgencia_con_db() -> None:
    plazo = MagicMock(spec=EntidadPlazo)
    plazo.dias_limite = 15
    plazo.dias_alerta = 3
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=plazo)
    resultado = await calcular_urgencia(
        db,
        fecha_recepcion=datetime(2025, 1, 1, tzinfo=UTC),
        entidad_nombre="SURA EPS",
        tipo_incapacidad="general",
        fecha_evaluacion=datetime(2025, 1, 20, tzinfo=UTC),
    )
    assert resultado == NivelUrgencia.ROJO.value


@pytest.mark.asyncio
async def test_cargar_indice_plazos() -> None:
    fila = MagicMock(spec=EntidadPlazo)
    fila.entidad_nombre = "Nueva EPS"
    fila.tipo_incapacidad = "general"
    fila.dias_limite = 5
    fila.dias_alerta = 1
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [fila]
    db = AsyncMock()
    db.scalars = AsyncMock(return_value=mock_scalars)
    indice = await cargar_indice_plazos(db)
    assert ("nueva eps", "general") in indice
