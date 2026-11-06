"""Pruebas del Agente de Impacto: métricas, tablero, KPIs de proceso y reporte por donante."""

from __future__ import annotations

from datetime import timedelta

import pytest

from comparte import reloj
from comparte.agentes.impacto import AgenteImpacto, metricas_de_items
from comparte.datos_demo import sembrar_actores
from comparte.modelos import Donacion, EstadoDonacion, EstadoOferta, Oferta


@pytest.fixture
def impacto(db):
    sembrar_actores(db)
    return AgenteImpacto(db)


def completada(db, impacto, kg=10.0, clave="pan", categoria="pan", donante_id=1, receptor_id=1,
               simulada=False, hace_dias=0, kg_recibidos=None) -> Donacion:
    ahora = reloj.ahora()
    d = Donacion(
        donante_id=donante_id, receptor_id=receptor_id, estado=EstadoDonacion.COMPLETADA,
        items=[{"nombre": clave, "clave": clave, "categoria": categoria, "kg": kg}], total_kg=kg,
        categoria_principal=categoria, caduca_en=ahora, recoleccion_desde=ahora, recoleccion_hasta=ahora,
        simulada=simulada, kg_recibidos=kg_recibidos, creada_en=ahora - timedelta(days=hace_dias),
    )
    db.add(d)
    db.flush()
    registro = impacto.registrar(d)
    registro.creado_en = ahora - timedelta(days=hace_dias)
    return d


class TestMetricas:
    def test_formulas(self):
        m = metricas_de_items([{"clave": "pan", "kg": 10.0}])
        assert m == {"kg": 10.0, "raciones": 20.0, "personas": 6.7, "co2e_kg": 16.0}

    def test_los_kg_confirmados_escalan_todo(self):
        m = metricas_de_items([{"clave": "pan", "kg": 10.0}, {"clave": "fruta", "kg": 10.0}], kg_confirmados=10.0)
        assert m["kg"] == 10.0 and m["raciones"] == 20.0
        assert m["co2e_kg"] == pytest.approx((10 * 1.6 + 10 * 0.8) / 2, abs=0.1)

    def test_item_desconocido_usa_factor_por_defecto(self):
        assert metricas_de_items([{"clave": "inventado", "kg": 5.0}])["co2e_kg"] == 10.0


class TestTablero:
    def test_totales_y_serie(self, db, impacto):
        completada(db, impacto, kg=10)
        completada(db, impacto, kg=30, clave="fruta", categoria="fruta", hace_dias=2)
        r = impacto.resumen()
        assert r["totales"]["rescates"] == 2 and r["totales"]["kg"] == 40.0
        assert r["totales"]["raciones"] == 80.0
        assert len(r["serie_diaria"]) == 30
        assert r["serie_diaria"][-1] == {"fecha": "2026-11-10", "kg": 10.0, "rescates": 1}
        assert r["serie_diaria"][-3]["kg"] == 30.0
        assert sum(d["kg"] for d in r["serie_diaria"]) == 40.0

    def test_agrupaciones(self, db, impacto):
        completada(db, impacto, kg=10, donante_id=1, receptor_id=1)  # Tlaquepaque -> Guadalajara
        completada(db, impacto, kg=5, donante_id=1, receptor_id=2, clave="fruta", categoria="fruta")
        completada(db, impacto, kg=8, donante_id=4, receptor_id=1)  # Zapopan -> Guadalajara
        r = impacto.resumen()
        assert [(f["etiqueta"], f["kg"]) for f in r["por_municipio_origen"]] == [("Tlaquepaque", 15.0), ("Zapopan", 8.0)]
        assert r["por_municipio_destino"][0]["etiqueta"] == "Guadalajara"
        assert r["por_categoria"][0]["etiqueta"] == "Pan y tortilla"
        assert r["top_donantes"][0] == {"clave": 1, "etiqueta": "Panadería La Espiga", "kg": 15.0, "rescates": 2}

    def test_se_puede_excluir_el_historial_simulado(self, db, impacto):
        completada(db, impacto, kg=10)
        completada(db, impacto, kg=100, simulada=True, hace_dias=3)
        assert impacto.resumen()["totales"]["kg"] == 110.0
        assert impacto.resumen(incluir_simuladas=False)["totales"]["kg"] == 10.0
        assert impacto.resumen()["simuladas"] == {"rescates": 1, "kg": 100.0}

    def test_filtra_por_donante_y_receptor(self, db, impacto):
        completada(db, impacto, kg=10, donante_id=1, receptor_id=1)
        completada(db, impacto, kg=20, donante_id=2, receptor_id=2)
        assert impacto.resumen(donante_id=2)["totales"]["kg"] == 20.0
        assert impacto.resumen(receptor_id=1)["totales"]["kg"] == 10.0

    def test_tablero_vacio_no_falla(self, impacto):
        r = impacto.resumen()
        assert r["totales"]["kg"] == 0 and r["kpis"]["tasa_completadas"] is None


class TestKpisDeProceso:
    def test_solo_cuentan_donaciones_reales(self, db, impacto):
        completada(db, impacto, simulada=True, hace_dias=5)
        assert impacto.resumen()["kpis"]["donaciones_reales"] == 0

    def test_tiempos_y_aceptacion_a_la_primera_oferta(self, db, impacto):
        ahora = reloj.ahora()
        for segundos, acepta_primera in ((40, True), (60, True), (80, False)):
            d = completada(db, impacto)
            d.segundos_registro = segundos
            d.primera_oferta_en = d.creada_en + timedelta(seconds=2)
            db.add(Oferta(donacion_id=d.id, receptor_id=1, creada_en=ahora, vence_en=ahora,
                          estado=EstadoOferta.ACEPTADA if acepta_primera else EstadoOferta.RECHAZADA))
        k = impacto.resumen()["kpis"]
        assert k["donaciones_reales"] == 3 and k["tasa_completadas"] == 1.0
        assert k["segundos_registro_mediana"] == 60
        assert k["segundos_primera_oferta_mediana"] == 2
        assert k["aceptacion_primera_oferta"] == pytest.approx(0.67, abs=0.01)


class TestReporteDeDonante:
    def test_incluye_totales_y_lista_de_rescates(self, db, impacto):
        completada(db, impacto, kg=10, donante_id=1)
        completada(db, impacto, kg=99, donante_id=2)
        rep = impacto.reporte_donante(1)
        assert rep["donante"]["nombre"] == "Panadería La Espiga"
        assert rep["resumen"]["totales"]["kg"] == 10.0
        assert len(rep["rescates"]) == 1 and rep["rescates"][0]["receptor"].startswith("Banco de Alimentos")

    def test_donante_inexistente(self, impacto):
        with pytest.raises(ValueError):
            impacto.reporte_donante(999)
