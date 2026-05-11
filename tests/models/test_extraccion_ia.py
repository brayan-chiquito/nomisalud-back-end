"""Contrato del modelo ExtraccionIA (SCRUM-128)."""

from sqlalchemy.orm import class_mapper

from app.models.extraccion_ia import ExtraccionIA


def test_extraccion_ia_tabla_y_columnas_clave():
    assert ExtraccionIA.__tablename__ == "extraccion_ia"
    cols = {c.key for c in ExtraccionIA.__table__.columns}
    assert "incapacidad_id" in cols
    assert "datos_extraidos" in cols
    assert "validaciones" in cols
    assert "raw_response" in cols


def test_extraccion_ia_incapacidad_id_es_unico():
    col = ExtraccionIA.__mapper__.columns["incapacidad_id"]
    assert col.unique is True


def test_extraccion_ia_relacion_incapacidad():
    rel = class_mapper(ExtraccionIA).relationships["incapacidad"]
    assert rel.back_populates == "extraccion_ia"
