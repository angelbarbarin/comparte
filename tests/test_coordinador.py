"""Pruebas del Agente Coordinador: puntaje, filtros duros, ofertas, rechazos y reasignación.

Hora de las pruebas: martes 10 de noviembre de 2026, 17:30. Donantes: 1 = Panadería La Espiga
(Tlaquepaque), 10 = Hotel Plaza Real (Guadalajara). Receptores: 1 Banco de Alimentos (con frío),
2 Comedor Santa Cecilia (sin frío), 3 Albergue (24 h, con frío), 4 Casa Hogar (con frío),
5 Comedor Los Pinos (cierra 18:00), 6 Nuevo Sol (sin verificar).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from comparte import reloj
from comparte.agentes.coordinador import PESOS, AgenteCoordinador
from comparte.datos_demo import sembrar_actores
from comparte.modelos import Donacion, EstadoDonacion, EstadoOferta, EventoAgente, Oferta

PAN = [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 25.0}]
POLLO = [{"nombre": "pollo", "clave": "pollo", "categoria": "proteina", "kg": 12.0}]


@pytest.fixture
def coord(db):
    sembrar_actores(db)
    return AgenteCoordinador(db)


def crear(db, items=PAN, donante_id=1, horas=6.0, frio=False, inocuidad=None) -> Donacion:
    ahora = reloj.ahora()
    d = Donacion(
        donante_id=donante_id, items=[dict(i) for i in items], total_kg=sum(i["kg"] for i in items),
        categoria_principal=items[0]["categoria"], requiere_frio=frio,
        caduca_en=ahora + timedelta(hours=horas), recoleccion_desde=ahora + timedelta(minutes=15),
        recoleccion_hasta=ahora + timedelta(hours=3), inocuidad=inocuidad or {}, creada_en=ahora,
    )
    db.add(d)
    db.flush()
    return d


def por_id(candidatos):
    return {c.receptor.id: c for c in candidatos}


class TestEvaluacion:
    def test_los_pesos_suman_uno(self):
        assert sum(PESOS.values()) == pytest.approx(1.0)

    def test_ordena_primero_los_viables_por_puntaje(self, db, coord):
        cands = coord.evaluar_receptores(crear(db))
        viables = [c for c in cands if c.viable]
        assert viables == cands[: len(viables)]
        assert [c.puntaje for c in viables] == sorted((c.puntaje for c in viables), reverse=True)
        assert all(0 <= c.puntaje <= 100 for c in cands)

    def test_receptor_sin_verificar_nunca_es_viable(self, db, coord):
        c = por_id(coord.evaluar_receptores(crear(db)))[6]
        assert not c.viable
        assert any("sin verificar" in m for m in c.motivos_exclusion)

    def test_cerrado_al_llegar(self, db, coord):
        c = por_id(coord.evaluar_receptores(crear(db)))[5]  # Los Pinos cierra 18:00; llegaría ~18:54
        assert not c.viable and any("cerrado al llegar" in m for m in c.motivos_exclusion)

    def test_cadena_de_frio_descarta_a_quien_no_tiene_refrigeracion(self, db, coord):
        cands = por_id(coord.evaluar_receptores(crear(db, POLLO, donante_id=10, horas=20, frio=True)))
        assert not cands[2].viable and any("sin refrigeración" in m for m in cands[2].motivos_exclusion)
        assert cands[3].viable  # el albergue sí tiene frío y necesita proteína

    def test_no_ofrece_a_quien_no_necesita_nada_de_lo_donado_si_hay_alternativas(self, db, coord):
        cands = por_id(coord.evaluar_receptores(crear(db, POLLO, donante_id=10, horas=20, frio=True)))
        assert any("no necesita" in m for m in cands[4].motivos_exclusion)  # Casa Hogar no pide proteína

    def test_capacidad_insuficiente(self, db, coord):
        grande = [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 150.0}]
        cands = por_id(coord.evaluar_receptores(crear(db, grande)))
        assert not cands[2].viable and any("capacidad insuficiente" in m for m in cands[2].motivos_exclusion)
        assert cands[1].viable  # el banco tiene 800 kg/día

    def test_no_llega_antes_de_caducar(self, db, coord):
        cands = por_id(coord.evaluar_receptores(crear(db, horas=1.0)))
        assert any("no llegaría antes de que caduque" in m for m in cands[2].motivos_exclusion)
        assert cands[1].viable  # el banco está a 4 km: llega con margen

    def test_limite_de_transporte_para_comida_preparada(self, db, coord):
        d = crear(db, inocuidad={"horas_max_transporte": 0.1})  # 6 minutos
        assert not [c for c in coord.evaluar_receptores(d) if c.viable]

    def test_la_necesidad_pesa_en_el_puntaje(self, db, coord):
        lacteos = [{"nombre": "leche", "clave": "lacteos", "categoria": "lacteos", "kg": 10.0}]
        cands = por_id(coord.evaluar_receptores(crear(db, lacteos, donante_id=10, horas=40, frio=True)))
        assert cands[4].componentes["necesidad"] == pytest.approx(1.0)  # Casa Hogar: lácteos prioridad 3
        assert cands[1].componentes["necesidad"] == pytest.approx(2 / 3)  # Banco: prioridad 2

    def test_la_equidad_baja_para_quien_ha_recibido_mucho(self, db, coord):
        antes = por_id(coord.evaluar_receptores(crear(db)))[3].componentes["equidad"]
        previa = crear(db, [{"nombre": "pan", "clave": "pan", "categoria": "pan", "kg": 100.0}])
        previa.estado, previa.receptor_id, previa.asignada_en = (
            EstadoDonacion.COMPLETADA, 3, reloj.ahora() - timedelta(days=2))
        despues = por_id(coord.evaluar_receptores(crear(db)))[3].componentes["equidad"]
        assert antes == pytest.approx(1.0) and despues < antes


class TestCicloDeOferta:
    def test_ofrece_al_mejor_viable_con_justificacion(self, db, coord):
        d = crear(db)
        oferta = coord.ofrecer(d)
        assert oferta.estado == EstadoOferta.PENDIENTE and oferta.receptor_id == 2  # Santa Cecilia
        assert d.estado == EstadoDonacion.OFRECIDA and d.primera_oferta_en == reloj.ahora()
        assert "Mejor de 4 receptores viables" in oferta.justificacion
        assert oferta.vence_en == reloj.ahora() + timedelta(minutes=15)
        assert d.evaluacion["candidatos"][0]["receptor_id"] == 2  # ranking guardado y explicable
        assert d.evaluacion["ronda"] == 1

    def test_aceptar_asigna_la_donacion(self, db, coord):
        d = crear(db)
        oferta = coord.ofrecer(d)
        coord.responder(oferta, aceptar=True)
        assert (d.estado, d.receptor_id, d.asignada_en) == (EstadoDonacion.ASIGNADA, 2, reloj.ahora())
        assert oferta.estado == EstadoOferta.ACEPTADA

    def test_rechazar_y_reasignar_al_siguiente(self, db, coord):
        d = crear(db)
        primera = coord.ofrecer(d)
        coord.responder(primera, aceptar=False, motivo="Sin espacio")
        segunda = coord.ofrecer(d)
        assert primera.estado == EstadoOferta.RECHAZADA and primera.motivo == "Sin espacio"
        assert segunda.receptor_id != primera.receptor_id and segunda.receptor_id == 1  # el banco
        assert d.evaluacion["ronda"] == 2
        acciones = [e.accion for e in db.query(EventoAgente).filter_by(donacion_id=d.id)]
        assert acciones == ["oferta_creada", "oferta_rechazada", "oferta_reasignada"]

    def test_si_todos_rechazan_queda_sin_receptor(self, db, coord):
        d = crear(db)
        for _ in range(10):
            oferta = coord.ofrecer(d)
            if oferta is None:
                break
            coord.responder(oferta, aceptar=False)
        assert d.estado == EstadoDonacion.SIN_RECEPTOR
        assert db.query(Oferta).filter_by(donacion_id=d.id).count() == 4  # los 4 viables, una vez cada uno

    def test_sin_receptor_viable_desde_el_inicio(self, db, coord):
        d = crear(db, horas=0.2)  # caduca en 12 min: nadie llega
        assert coord.ofrecer(d) is None and d.estado == EstadoDonacion.SIN_RECEPTOR

    def test_responder_dos_veces_la_misma_oferta_falla(self, db, coord):
        oferta = coord.ofrecer(crear(db))
        coord.responder(oferta, aceptar=True)
        with pytest.raises(ValueError):
            coord.responder(oferta, aceptar=False)

    def test_oferta_sin_respuesta_expira_a_los_15_minutos(self, db, coord):
        oferta = coord.ofrecer(crear(db))
        assert coord.expirar_vencidas() == []  # todavía vigente
        reloj.avanzar(16)
        vencidas = coord.expirar_vencidas()
        assert vencidas == [oferta] and oferta.estado == EstadoOferta.EXPIRADA

    def test_la_capacidad_reservada_por_ofertas_pendientes_cuenta(self, db, coord):
        # Santa Cecilia (80 kg/día): una oferta pendiente de 25 kg reserva espacio
        coord.ofrecer(crear(db))
        c = por_id(coord.evaluar_receptores(crear(db)))[2]
        assert c.kg_disponibles == pytest.approx(55.0)
