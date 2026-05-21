"""Tests de rango de periodo para conciliación."""

import pytest

from app.services.conciliacion_periodo import rango_periodo_mes_anio


def test_rango_febrero_bisiesto():
    r = rango_periodo_mes_anio(mes=2, anio=2024)
    assert r.mes == 2
    assert r.fin.day == 29


def test_mes_invalido():
    with pytest.raises(ValueError, match="mes"):
        rango_periodo_mes_anio(mes=13, anio=2024)
