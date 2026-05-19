"""Modelo Inconsistencia (SCRUM-170)."""

from sqlalchemy.orm import class_mapper

from app.models.inconsistencia import Inconsistencia


def test_inconsistencia_tabla_y_columnas_clave():
    assert Inconsistencia.__tablename__ == "inconsistencias"
    cols = {c.key for c in class_mapper(Inconsistencia).columns}
    assert {"id", "incapacidad_id", "tipo", "descripcion", "created_at"} <= cols


def test_inconsistencia_relacion_incapacidad():
    rel = class_mapper(Inconsistencia).relationships["incapacidad"]
    assert rel.back_populates == "inconsistencias"
