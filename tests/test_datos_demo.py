"""El piloto simulado debe cumplir lo prometido en el documento de visión (>=10 donantes y >=5 receptores)."""

from __future__ import annotations

from sqlalchemy import func, select

from comparte.conocimiento.catalogo import CATEGORIAS
from comparte.datos_demo import sembrar_actores
from comparte.modelos import Donante, Receptor, Voluntario


def test_siembra_cumple_el_piloto_simulado(db):
    conteos = sembrar_actores(db)
    assert db.scalar(select(func.count(Donante.id))) >= 10
    assert db.scalar(select(func.count(Receptor.id))) >= 5
    assert db.scalar(select(func.count(Voluntario.id))) >= 5
    assert conteos["donantes"] == 10


def test_sembrar_dos_veces_no_duplica(db):
    sembrar_actores(db)
    assert sembrar_actores(db) == {"donantes": 0, "receptores": 0, "voluntarios": 0}
    assert db.scalar(select(func.count(Donante.id))) == 10


def test_hay_un_receptor_sin_verificar_para_la_demo(db):
    sembrar_actores(db)
    sin_verificar = db.scalars(select(Receptor).where(Receptor.verificado.is_(False))).all()
    assert len(sin_verificar) == 1


def test_las_necesidades_usan_categorias_validas(db):
    sembrar_actores(db)
    for receptor in db.scalars(select(Receptor)):
        assert set(receptor.necesidades) <= set(CATEGORIAS), receptor.nombre
        assert all(1 <= p <= 3 for p in receptor.necesidades.values())


def test_las_coordenadas_estan_en_el_amg(db):
    sembrar_actores(db)
    for entidad in (*db.scalars(select(Donante)), *db.scalars(select(Receptor)), *db.scalars(select(Voluntario))):
        assert 20.3 < entidad.lat < 20.9 and -103.7 < entidad.lon < -103.0, entidad.nombre
