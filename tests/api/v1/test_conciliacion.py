"""Tests HTTP de conciliación (SCRUM-189 / SCRUM-190)."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.user import UserRole
from app.schemas.conciliacion import (
    ConciliacionResponse,
    ConciliacionResumenEntidadItem,
)
from app.services.conciliacion_service import ConciliacionError, _DatosConciliacion


def _token(role: UserRole) -> str:
    uid = uuid.uuid4()
    return create_access_token(
        uid,
        role.value,
        f"rrhh-{uid.hex[:8]}@test.local",
    )


@pytest.mark.asyncio
class TestConciliacionApi:
    async def test_get_403_colaborador(self, client: AsyncClient):
        token = _token(UserRole.COLABORADOR)
        r = await client.get(
            "/api/v1/conciliacion",
            headers={"Authorization": f"Bearer {token}"},
            params={"entidad": "Nomi", "mes": 5, "anio": 2024},
        )
        assert r.status_code == 403

    async def test_get_200_mock(self, client: AsyncClient):
        token = _token(UserRole.ADMIN)
        resp = ConciliacionResponse(
            entidad="Nomi",
            mes=5,
            anio=2024,
            total_cobrado=Decimal("100"),
            total_pagado=Decimal("100"),
            diferencia=Decimal("0"),
            cantidad_cobrada_periodo=1,
            cantidad_pendiente_pago=0,
            pendientes=[],
            detalle=[],
        )
        datos = _DatosConciliacion(
            response=resp,
            resumen_entidad=ConciliacionResumenEntidadItem(
                entidad="Nomi",
                total_cobrado=Decimal("100"),
                total_pagado=Decimal("100"),
                diferencia=Decimal("0"),
                cantidad_cobrada_periodo=1,
                cantidad_pendiente_pago=0,
            ),
        )
        with patch(
            "app.api.v1.routes.conciliacion.obtener_conciliacion",
            new_callable=AsyncMock,
            return_value=datos,
        ):
            r = await client.get(
                "/api/v1/conciliacion",
                headers={"Authorization": f"Bearer {token}"},
                params={"entidad": "Nomi", "mes": 5, "anio": 2024},
            )
        assert r.status_code == 200
        body = r.json()
        assert body["entidad"] == "Nomi"
        assert body["total_pagado"] == "100"

    async def test_exportar_200_mock(self, client: AsyncClient):
        token = _token(UserRole.COORDINADOR_RRHH)
        with (
            patch(
                "app.api.v1.routes.conciliacion.obtener_resumen_multientidad",
                new_callable=AsyncMock,
                return_value=([], []),
            ),
            patch(
                "app.api.v1.routes.conciliacion.generar_xlsx_conciliacion",
                return_value=b"PK\x03\x04fake",
            ),
        ):
            r = await client.get(
                "/api/v1/conciliacion/exportar",
                headers={"Authorization": f"Bearer {token}"},
                params={"mes": 6, "anio": 2024},
            )
        assert r.status_code == 200
        assert (
            r.headers["content-type"]
            == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "attachment" in r.headers.get("content-disposition", "")

    async def test_get_422_conciliacion_error(self, client: AsyncClient):
        token = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.conciliacion.obtener_conciliacion",
            new_callable=AsyncMock,
            side_effect=ConciliacionError(422, "mes inválido"),
        ):
            r = await client.get(
                "/api/v1/conciliacion",
                headers={"Authorization": f"Bearer {token}"},
                params={"entidad": "Nomi", "mes": 13, "anio": 2024},
            )
        assert r.status_code == 422

    async def test_exportar_con_entidad_mock(self, client: AsyncClient):
        token = _token(UserRole.AUXILIAR_RRHH)
        resp = ConciliacionResponse(
            entidad="EPS",
            mes=3,
            anio=2024,
            total_cobrado=Decimal("10"),
            total_pagado=Decimal("10"),
            diferencia=Decimal("0"),
            cantidad_cobrada_periodo=0,
            cantidad_pendiente_pago=0,
            pendientes=[],
            detalle=[],
        )
        datos = _DatosConciliacion(
            response=resp,
            resumen_entidad=ConciliacionResumenEntidadItem(
                entidad="EPS",
                total_cobrado=Decimal("10"),
                total_pagado=Decimal("10"),
                diferencia=Decimal("0"),
                cantidad_cobrada_periodo=0,
                cantidad_pendiente_pago=0,
            ),
        )
        with (
            patch(
                "app.api.v1.routes.conciliacion.obtener_conciliacion",
                new_callable=AsyncMock,
                return_value=datos,
            ),
            patch(
                "app.api.v1.routes.conciliacion.generar_xlsx_conciliacion",
                return_value=b"xlsx",
            ),
        ):
            r = await client.get(
                "/api/v1/conciliacion/exportar",
                headers={"Authorization": f"Bearer {token}"},
                params={"entidad": "EPS", "mes": 3, "anio": 2024},
            )
        assert r.status_code == 200
        assert "conciliacion_2024_03.xlsx" in r.headers.get("content-disposition", "")

    async def test_exportar_422_conciliacion_error(self, client: AsyncClient):
        token = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.conciliacion.obtener_resumen_multientidad",
            new_callable=AsyncMock,
            side_effect=ConciliacionError(422, "anio inválido"),
        ):
            r = await client.get(
                "/api/v1/conciliacion/exportar",
                headers={"Authorization": f"Bearer {token}"},
                params={"mes": 1, "anio": 1999},
            )
        assert r.status_code == 422
