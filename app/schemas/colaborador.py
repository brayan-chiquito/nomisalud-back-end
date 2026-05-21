"""Esquemas de búsqueda de colaboradores (SCRUM-197)."""

from uuid import UUID

from pydantic import BaseModel, Field


class ColaboradorBusquedaItem(BaseModel):
    """Resultado de autocompletado para selector de colaborador."""

    id: UUID
    nombre_completo: str | None = None
    numero_documento: str | None = None
    email: str


class ColaboradorBusquedaResponse(BaseModel):
    items: list[ColaboradorBusquedaItem] = Field(default_factory=list)
