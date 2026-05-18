"""Contrato del modelo HistorialEstado (SCRUM-138)."""

from sqlalchemy.orm import class_mapper

from app.models.historial_estado import HistorialEstado


def test_historial_estado_tabla_y_columnas_auditoria() -> None:
    assert HistorialEstado.__tablename__ == "historial_estados"
    cols = {c.key for c in HistorialEstado.__table__.columns}
    assert "incapacidad_id" in cols
    assert "estado_anterior" in cols
    assert "estado_nuevo" in cols
    assert "user_id" in cols
    assert "timestamp" in cols


def test_historial_estado_incapacidad_id_no_es_unico() -> None:
    col = HistorialEstado.__mapper__.columns["incapacidad_id"]
    assert col.unique is not True


def test_historial_estado_fk_incapacidad() -> None:
    col = HistorialEstado.__table__.c.incapacidad_id
    fk_targets = {fk.column.table.name for fk in col.foreign_keys}
    assert fk_targets == {"incapacidades"}


def test_historial_estado_fk_user() -> None:
    col = HistorialEstado.__table__.c.user_id
    fk_targets = {fk.column.table.name for fk in col.foreign_keys}
    assert fk_targets == {"users"}


def test_historial_estado_relaciones() -> None:
    m = class_mapper(HistorialEstado)
    assert m.relationships["incapacidad"].back_populates == "historial_estados"
    assert m.relationships["usuario"].back_populates == "historial_estados"
