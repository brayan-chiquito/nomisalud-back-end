"""Tests HTTP de pagos (SCRUM-185 / SCRUM-186)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.pago import Pago, PagoEstado
from app.models.user import UserRole


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"rrhh-{uid.hex[:8]}@test.local",
    )


@pytest.mark.asyncio
class TestPagosApi:
    async def test_post_403_colaborador(self, client: AsyncClient):
        token = _token(UserRole.COLABORADOR)
        r = await client.post(
            "/api/v1/pagos",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "entidad_origen": "NomiSalud",
                "referencia": "PAY-1",
                "monto": "500000.00",
                "radicados": ["IN0123456789ABCDEF0"],
            },
        )
        assert r.status_code == 403

    async def test_post_201_mock(self, client: AsyncClient):
        token = _token(UserRole.ADMIN)
        pago = MagicMock(spec=Pago)
        pago.id = uuid.uuid4()
        pago.entidad_origen = "Nomi"
        pago.referencia = "R1"
        pago.monto = Decimal("100.00")
        from datetime import datetime

        pago.fecha_operacion = datetime.now()

        with patch(
            "app.api.v1.routes.pagos.registrar_pago_y_marcar_pagadas",
            new_callable=AsyncMock,
            return_value=pago,
        ) as m:
            r = await client.post(
                "/api/v1/pagos",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "entidad_origen": "Nomi",
                    "referencia": "R1",
                    "monto": "100.00",
                    "radicados": ["IN01"],
                },
            )
        assert r.status_code == 201
        m.assert_awaited_once()

    async def test_get_list_mock(self, client: AsyncClient):
        token = _token(UserRole.COORDINADOR_RRHH)
        p = MagicMock(spec=Pago)
        p.id = uuid.uuid4()
        p.entidad_origen = "E"
        p.referencia = "R"
        p.monto = Decimal("1.00")
        from datetime import datetime

        p.fecha_operacion = datetime.now()
        p.estado = PagoEstado.REGISTRADO
        p.user_id = uuid.uuid4()
        with patch(
            "app.api.v1.routes.pagos.listar_pagos_paginado",
            new_callable=AsyncMock,
            return_value=([(p, 2)], 1),
        ):
            r = await client.get(
                "/api/v1/pagos?page=1",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["incapacidades_vinculadas"] == 2
