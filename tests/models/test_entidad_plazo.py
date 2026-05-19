"""Modelo EntidadPlazo (SCRUM-173)."""

from sqlalchemy.orm import class_mapper

from app.models.entidad_plazo import EntidadPlazo


def test_entidad_plazo_tabla_y_columnas() -> None:
    assert EntidadPlazo.__tablename__ == "entidades_plazos"
    cols = {c.key for c in class_mapper(EntidadPlazo).columns}
    assert {
        "id",
        "entidad_nombre",
        "tipo_incapacidad",
        "valor_limite",
        "unidad_limite",
        "dias_limite",
        "dias_alerta",
        "created_at",
        "updated_at",
    } <= cols
