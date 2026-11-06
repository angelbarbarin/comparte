"""Pruebas del Agente Logístico: elección de voluntario, ruta, ciclo de la recolección.

Voluntarios sembrados: 1 Mariana (auto 40 kg), 2 Carlos (camioneta 300 kg, hielera), 3 Fernanda
(moto 15 kg), 4 Luis (auto 50 kg, hielera), 5 Sofía (camioneta 200 kg), 6 Andrés (bicicleta 10 kg).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from comparte import reloj
from comparte.agentes.logistico import AgenteLogistico
from comparte.datos_demo import sembrar_actores
from comparte.modelos import (
    Donacion,
    EstadoDonacion,
    EstadoRecoleccion,
    Voluntario,
)


@pytest.fixture
def log(db):
    sembrar_actores(db)
    return AgenteLogistico(db)


def asignada(db, kg=25.0, donante_id=1, receptor_id=1, frio=False, horas=8.0, ventana_min=180) -> Donacion:
    """Donación ya aceptada por un receptor (por defecto: La Espiga -> Banco de Alimentos)."""
    ahora = reloj.ahora()
    d = Donacion(
        donante_id=donante_id, receptor_id=receptor_id, estado=EstadoDonacion.ASIGNADA,
        items=[{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": kg}], total_kg=kg,
        categoria_principal="pan", requiere_frio=frio, caduca_en=ahora + timedelta(hours=horas),
        recoleccion_desde=ahora + timedelta(minutes=10), recoleccion_hasta=ahora + timedelta(minutes=ventana_min),
        inocuidad={}, creada_en=ahora, asignada_en=ahora,
    )
    db.add(d)
    db.flush()
    return d


def por_id(candidatos):
    return {c.voluntario.id: c for c in candidatos}


class TestEvaluacion:
    def test_descarta_vehiculos_sin_capacidad(self, db, log):
        c = por_id(log.evaluar_voluntarios(asignada(db, kg=25)))
        assert not c[3].viable and "carga 15 kg" in c[3].motivos_exclusion[0]  # moto
        assert not c[6].viable  # bicicleta
        assert c[2].viable and c[1].viable

    def test_la_cadena_de_frio_exige_hielera(self, db, log):
        c = por_id(log.evaluar_voluntarios(asignada(db, kg=12, frio=True)))
        assert {i for i, x in c.items() if x.viable} == {2, 4}  # Carlos y Luis tienen hielera
        assert any("sin hielera" in m for m in c[1].motivos_exclusion)

    def test_ordena_viables_por_menor_tiempo_total(self, db, log):
        cands = log.evaluar_voluntarios(asignada(db))
        viables = [c for c in cands if c.viable]
        assert cands[: len(viables)] == viables
        assert [c.duracion_total_min for c in viables] == sorted(c.duracion_total_min for c in viables)

    def test_ruta_tiene_tres_puntos_y_dos_tramos_consistentes(self, db, log):
        mejor = log.evaluar_voluntarios(asignada(db))[0]
        ruta = mejor.ruta
        assert [p["rol"] for p in ruta["puntos"]] == ["voluntario", "donante", "receptor"]
        assert [(t["de"], t["a"]) for t in ruta["tramos"]] == [("voluntario", "donante"), ("donante", "receptor")]
        assert ruta["distancia_km"] == pytest.approx(sum(t["km"] for t in ruta["tramos"]), abs=0.15)
        assert mejor.entrega > mejor.recoger >= reloj.ahora()

    def test_fuera_de_horario(self, db, log):
        reloj.congelar(datetime(2026, 11, 10, 23, 0))  # todos terminan su turno antes de las 22:00
        d = asignada(db, receptor_id=3)  # el albergue abre 24 h, así que el receptor no estorba
        d.recoleccion_hasta = reloj.ahora() + timedelta(hours=4)
        cands = log.evaluar_voluntarios(d)
        assert not any(c.viable for c in cands)
        assert all(any("fuera de su horario" in m for m in c.motivos_exclusion) for c in cands)

    def test_ventana_de_recoleccion_muy_corta(self, db, log):
        d = asignada(db, ventana_min=11)  # solo 11 min: nadie llega a Tlaquepaque a tiempo salvo muy cerca
        cands = por_id(log.evaluar_voluntarios(d))
        assert any("ventana de recolección" in m for m in cands[2].motivos_exclusion)  # Carlos, desde Zapopan

    def test_no_alcanza_a_entregar_antes_de_que_cierre_el_receptor(self, db, log):
        reloj.congelar(datetime(2026, 11, 10, 18, 40))  # el Banco cierra a las 19:00
        d = asignada(db)
        cands = log.evaluar_voluntarios(d)
        assert not any(c.viable for c in cands)
        assert any("ya habría cerrado" in m for c in cands for m in c.motivos_exclusion)

    def test_no_alcanza_a_entregar_antes_de_caducar(self, db, log):
        cands = log.evaluar_voluntarios(asignada(db, horas=0.4))
        assert any("antes de que caduque" in m for c in cands for m in c.motivos_exclusion)


class TestCiclo:
    def test_proponer_aceptar_recoger_entregar(self, db, log):
        d = asignada(db)
        rec = log.proponer(d)
        assert rec.estado == EstadoRecoleccion.PROPUESTA and d.estado == EstadoDonacion.ASIGNADA
        assert rec.vence_en == reloj.ahora() + timedelta(minutes=10)

        log.responder(rec, aceptar=True)
        assert (rec.estado, d.estado) == (EstadoRecoleccion.ACEPTADA, EstadoDonacion.EN_RECOLECCION)
        log.avanzar(rec, EstadoRecoleccion.RECOGIDA)
        assert (rec.estado, d.estado) == (EstadoRecoleccion.RECOGIDA, EstadoDonacion.EN_CAMINO)
        log.avanzar(rec, EstadoRecoleccion.ENTREGADA)
        assert (rec.estado, d.estado) == (EstadoRecoleccion.ENTREGADA, EstadoDonacion.ENTREGADA)
        assert d.entregada_en == reloj.ahora()

    def test_no_se_puede_saltar_pasos(self, db, log):
        rec = log.proponer(asignada(db))
        with pytest.raises(ValueError):
            log.avanzar(rec, EstadoRecoleccion.ENTREGADA)  # ni siquiera la aceptó
        log.responder(rec, aceptar=True)
        with pytest.raises(ValueError):
            log.avanzar(rec, EstadoRecoleccion.ENTREGADA)  # aún no la recoge

    def test_rechazo_reasigna_a_otro_voluntario(self, db, log):
        d = asignada(db)
        primera = log.proponer(d)
        log.responder(primera, aceptar=False, motivo="Tengo un imprevisto")
        segunda = log.proponer(d)
        assert primera.estado == EstadoRecoleccion.RECHAZADA
        assert segunda.voluntario_id != primera.voluntario_id

    def test_un_voluntario_no_toma_dos_recolecciones_a_la_vez(self, db, log):
        primera = log.proponer(asignada(db, donante_id=1))
        segunda = log.proponer(asignada(db, donante_id=2, receptor_id=1))
        assert segunda.voluntario_id != primera.voluntario_id

    def test_sin_voluntarios_la_donacion_queda_sin_voluntario(self, db, log):
        for v in db.scalars(select(Voluntario)):
            v.disponible = False
        d = asignada(db)
        assert log.proponer(d) is None and d.estado == EstadoDonacion.SIN_VOLUNTARIO

    def test_propuesta_sin_respuesta_expira(self, db, log):
        rec = log.proponer(asignada(db))
        assert log.expirar_vencidas() == []
        reloj.avanzar(11)
        assert log.expirar_vencidas() == [rec] and rec.estado == EstadoRecoleccion.EXPIRADA
