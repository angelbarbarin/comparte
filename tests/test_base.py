"""Pruebas de la infraestructura base: reloj, geografía y creación del esquema."""

from __future__ import annotations

from datetime import datetime

import pytest

from comparte import geo, reloj
from comparte.modelos import Donacion, Donante, EstadoDonacion


class TestReloj:
    def test_congelado_devuelve_la_hora_fija(self, reloj_congelado):
        assert reloj.ahora() == reloj_congelado

    def test_avanzar_mueve_el_reloj_congelado(self, reloj_congelado):
        reloj.avanzar(20)
        assert reloj.ahora() == datetime(2026, 11, 10, 17, 50)

    def test_fijar_hora_hoy_sigue_corriendo_desde_esa_hora(self):
        reloj.restablecer()
        fijada = reloj.fijar_hora_hoy("17:30")
        assert (fijada.hour, fijada.minute) == (17, 30)
        # sigue corriendo: unos instantes después sigue siendo ~17:30, no se queda congelado
        assert 0 <= (reloj.ahora() - fijada).total_seconds() < 5
        assert reloj.hay_desfase()

    def test_restablecer_quita_el_desfase(self):
        reloj.fijar_hora_hoy("03:00")
        reloj.restablecer()
        assert not reloj.hay_desfase()

    def test_fin_del_dia(self):
        assert reloj.fin_del_dia(datetime(2026, 11, 10, 8, 0)) == datetime(2026, 11, 10, 23, 59)


class TestGeo:
    def test_misma_coordenada_es_cero(self):
        assert geo.haversine_km(20.67, -103.35, 20.67, -103.35) == pytest.approx(0.0)

    def test_distancia_centro_gdl_a_zapopan_es_razonable(self):
        # Centro de Guadalajara -> centro de Zapopan: ~5 km en línea recta
        km = geo.haversine_km(20.6767, -103.3475, 20.7236, -103.3848)
        assert 5.0 < km < 8.0

    def test_distancia_por_calles_es_mayor_que_en_linea_recta(self):
        recta = geo.haversine_km(20.6767, -103.3475, 20.7236, -103.3848)
        calles = geo.distancia_calles_km(20.6767, -103.3475, 20.7236, -103.3848, 1.3)
        assert calles == pytest.approx(recta * 1.3)

    def test_minutos_de_viaje(self):
        assert geo.minutos_de_viaje(25, 25) == pytest.approx(60)
        with pytest.raises(ValueError):
            geo.minutos_de_viaje(5, 0)


class TestEsquema:
    def test_se_pueden_guardar_y_leer_donante_y_donacion(self, db):
        donante = Donante(nombre="Panadería Demo", giro="panaderia", direccion="Calle 1",
                          municipio="Tlaquepaque", lat=20.64, lon=-103.31)
        db.add(donante)
        db.flush()
        ahora = reloj.ahora()
        donacion = Donacion(
            donante_id=donante.id, estado=EstadoDonacion.OFRECIDA,
            items=[{"nombre": "pan", "kg": 10.0}], total_kg=10.0,
            caduca_en=reloj.fin_del_dia(ahora), recoleccion_desde=ahora,
            recoleccion_hasta=ahora, creada_en=ahora,
        )
        db.add(donacion)
        db.commit()

        leida = db.get(Donacion, donacion.id)
        assert leida.donante.nombre == "Panadería Demo"
        assert leida.items[0]["kg"] == 10.0
        assert leida.estado in EstadoDonacion.ACTIVAS
