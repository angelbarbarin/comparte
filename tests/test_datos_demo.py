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


class TestHistorialSimulado:
    def test_crea_rescates_completados_y_marcados_como_simulados(self, db):
        from datetime import timedelta

        from comparte import reloj
        from comparte.datos_demo import sembrar_historial
        from comparte.modelos import Donacion, EstadoDonacion, RegistroImpacto

        sembrar_actores(db)
        assert sembrar_historial(db, cantidad=40) == 40
        donaciones = db.scalars(select(Donacion)).all()
        assert len(donaciones) == 40
        assert all(d.simulada and d.estado == EstadoDonacion.COMPLETADA for d in donaciones)
        assert all(reloj.ahora() - timedelta(days=31) < d.creada_en < reloj.ahora() for d in donaciones)
        assert db.scalar(select(func.count(RegistroImpacto.id))) == 40
        # nunca se asigna a un receptor sin verificar
        assert all(d.receptor_id != 6 for d in donaciones)

    def test_es_determinista(self, db, motor):
        from comparte.datos_demo import sembrar_historial
        from comparte.db import crear_fabrica, crear_motor, crear_tablas
        from comparte.modelos import Donacion

        sembrar_actores(db)
        sembrar_historial(db, cantidad=15, semilla=7)
        primera = [(d.donante_id, d.receptor_id, d.total_kg) for d in db.scalars(select(Donacion).order_by(Donacion.id))]

        otro_motor = crear_motor("sqlite://")
        crear_tablas(otro_motor)
        otra = crear_fabrica(otro_motor)()
        sembrar_actores(otra)
        sembrar_historial(otra, cantidad=15, semilla=7)
        segunda = [(d.donante_id, d.receptor_id, d.total_kg) for d in otra.scalars(select(Donacion).order_by(Donacion.id))]
        assert primera == segunda

    def test_sin_actores_no_hace_nada(self, db):
        from comparte.datos_demo import sembrar_historial

        assert sembrar_historial(db) == 0

    def test_el_tablero_los_cuenta_y_los_rotula(self, db):
        from comparte.agentes.impacto import AgenteImpacto
        from comparte.datos_demo import sembrar_historial

        sembrar_actores(db)
        sembrar_historial(db, cantidad=40)
        r = AgenteImpacto(db).resumen()
        assert r["totales"]["rescates"] == 40 and r["simuladas"]["rescates"] == 40
        assert r["totales"]["kg"] > 500
        assert r["kpis"]["donaciones_reales"] == 0  # el historial no contamina los KPIs de proceso
