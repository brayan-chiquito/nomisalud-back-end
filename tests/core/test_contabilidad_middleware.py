"""Tests del middleware de restricción para rol contabilidad (SCRUM-200)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.contabilidad_middleware import (
    _rol_desde_authorization,
    _ruta_bloqueada_para_contabilidad,
)
from app.core.security import create_access_token
from app.main import app
from app.models.user import UserRole


def test_ruta_bloqueada_incapacidades_y_colaboradores() -> None:
    assert _ruta_bloqueada_para_contabilidad("/api/v1/incapacidades") is True
    assert _ruta_bloqueada_para_contabilidad("/api/v1/incapacidades/upload") is True
    assert _ruta_bloqueada_para_contabilidad("/api/v1/colaboradores/buscar") is True
    assert _ruta_bloqueada_para_contabilidad("/api/v1/pagos") is False
    assert _ruta_bloqueada_para_contabilidad("/api/v1/conciliacion") is False


def test_rol_desde_authorization_contabilidad() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(),
        role=UserRole.CONTABILIDAD.value,
        email="c@test.local",
    )
    assert _rol_desde_authorization(f"Bearer {token}") == UserRole.CONTABILIDAD


@pytest.mark.asyncio
class TestContabilidadMiddlewareIntegracion:
    async def test_403_incapacidades_con_rol_contabilidad(self) -> None:
        token = create_access_token(
            user_id=uuid.uuid4(),
            role=UserRole.CONTABILIDAD.value,
            email="contabilidad@test.local",
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/incapacidades",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403
        assert "contabilidad" in response.json()["detail"].lower()

    async def test_403_colaboradores_buscar(self) -> None:
        token = create_access_token(
            user_id=uuid.uuid4(),
            role=UserRole.CONTABILIDAD.value,
            email="contabilidad@test.local",
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/colaboradores/buscar?q=juan",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 403

    async def test_conciliacion_permitida_para_contabilidad(self) -> None:
        token = create_access_token(
            user_id=uuid.uuid4(),
            role=UserRole.CONTABILIDAD.value,
            email="contabilidad@test.local",
        )
        with patch(
            "app.api.v1.routes.conciliacion.obtener_conciliacion",
            new_callable=AsyncMock,
        ) as mock_conc:
            from app.schemas.conciliacion import ConciliacionResponse
            from app.services.conciliacion_service import _DatosConciliacion

            resp = ConciliacionResponse(
                entidad="EPS",
                mes=1,
                anio=2026,
                total_cobrado=Decimal("0"),
                total_pagado=Decimal("0"),
                diferencia=Decimal("0"),
                cantidad_cobrada_periodo=0,
                cantidad_pendiente_pago=0,
                pendientes=[],
                detalle=[],
            )
            mock_conc.return_value = _DatosConciliacion(
                response=resp,
                resumen_entidad=None,
            )
            transport = ASGITransport(app=app)
            base = "http://test"
            async with AsyncClient(transport=transport, base_url=base) as client:
                response = await client.get(
                    "/api/v1/conciliacion",
                    params={"entidad": "EPS", "mes": 1, "anio": 2026},
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert response.status_code == 200
