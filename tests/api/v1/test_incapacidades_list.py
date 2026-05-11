"""Tests del endpoint GET /api/v1/incapacidades."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token
from app.models.incapacidad import ArchivoTipo, Incapacidad, IncapacidadEstado
from app.models.user import UserRole
from app.services.incapacidad_list_service import IncapacidadListRow


def _token(role: UserRole, user_id: uuid.UUID | None = None) -> tuple[str, uuid.UUID]:
    uid = user_id or uuid.uuid4()
    return (
        create_access_token(
            uid,
            role.value,
            f"user-{uid.hex[:8]}@test.local",
        ),
        uid,
    )


@pytest.mark.asyncio
class TestIncapacidadesListGet:
    async def test_200_items_total_pages(self, client: AsyncClient):
        token, uid = _token(UserRole.COLABORADOR, uuid.uuid4())
        iid = uuid.uuid4()
        recv = datetime(2025, 3, 1, 12, 0, tzinfo=UTC)
        row = MagicMock(spec=Incapacidad)
        row.id = iid
        row.radicado = "IN0123456789ABCDEF0"
        row.estado = IncapacidadEstado.TRANSCRITA
        row.colaborador_id = uid
        row.archivo_tipo = ArchivoTipo.PDF
        row.fecha_recepcion = recv

        list_row = IncapacidadListRow(
            incapacidad=row,
            colaborador_nombre="María López",
            colaborador_email="maria@test.local",
            entidad_nombre="EPS Sura",
            entidad_tipo="EPS",
            entidad_nit="800123456",
            entidad_ciudad="Medellín",
            incapacidad_tipo_extraido="enfermedad_general",
        )

        with patch(
            "app.api.v1.routes.incapacidades.list_incapacidades_paginated",
            new_callable=AsyncMock,
            return_value=([list_row], 45),
        ) as list_mock:
            response = await client.get(
                "/api/v1/incapacidades?page=2&estado=transcrita",
                headers={"Authorization": f"Bearer {token}"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 45
        assert body["pages"] == 3
        assert len(body["items"]) == 1
        assert body["items"][0] == {
            "id": str(iid),
            "radicado": "IN0123456789ABCDEF0",
            "estado": "transcrita",
            "colaborador_id": str(uid),
            "colaborador_nombre": "María López",
            "colaborador_email": "maria@test.local",
            "archivo_tipo": "pdf",
            "fecha_recepcion": recv.isoformat().replace("+00:00", "Z"),
            "entidad_nombre": "EPS Sura",
            "entidad_tipo": "EPS",
            "entidad_nit": "800123456",
            "entidad_ciudad": "Medellín",
            "incapacidad_tipo_extraido": "enfermedad_general",
        }
        list_mock.assert_awaited_once()
        call_kw = list_mock.await_args.kwargs
        assert call_kw["page"] == 2
        assert call_kw["estado"] == IncapacidadEstado.TRANSCRITA
        assert call_kw["colaborador_id_scope"] == uid

    async def test_rrhh_sin_scope_colaborador(self, client: AsyncClient):
        token, _ = _token(UserRole.COORDINADOR_RRHH, uuid.uuid4())
        with patch(
            "app.api.v1.routes.incapacidades.list_incapacidades_paginated",
            new_callable=AsyncMock,
            return_value=([], 0),
        ) as list_mock:
            response = await client.get(
                "/api/v1/incapacidades",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        assert list_mock.await_args.kwargs["colaborador_id_scope"] is None

    async def test_422_estado_invalido(self, client: AsyncClient):
        token, _ = _token(UserRole.ADMIN)
        with patch(
            "app.api.v1.routes.incapacidades.list_incapacidades_paginated",
            new_callable=AsyncMock,
        ) as list_mock:
            response = await client.get(
                "/api/v1/incapacidades?estado=no_existe",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 422
        list_mock.assert_not_called()

    async def test_401_sin_token(self, client: AsyncClient):
        response = await client.get("/api/v1/incapacidades")
        assert response.status_code == 403
