"""Pruebas de flujo completo: el orquestador coordinando a los cuatro agentes.

Cada escenario corresponde a una parte del guion del video (docs/GUION_VIDEO.md).
Hora de las pruebas: martes 10 de noviembre de 2026, 17:30.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from comparte import reloj
from comparte.datos_demo import sembrar_actores
from comparte.llm import ExtractorReglas
from comparte.modelos import (
    Conversacion,
    Donacion,
    EstadoDonacion,
    EstadoOferta,
    EstadoRecoleccion,
    EventoAgente,
    Oferta,
    Receptor,
    RegistroImpacto,
    Recoleccion,
    Voluntario,
)
from comparte.orquestador import Orquestador


@pytest.fixture
def orq(db, ajustes_prueba):
    sembrar_actores(db)
    return Orquestador(db, extractor=ExtractorReglas(), ajustes=ajustes_prueba)


def donar(orq, texto: str, donante_id: int = 1, *respuestas: str) -> Donacion:
    """Conversación de un donante: describe, y responde lo que se le pregunte hasta que se registre."""
    conv = orq.iniciar_conversacion(donante_id)
    resultado = orq.mensaje_donante(conv.id, texto)
    for r in respuestas:
        resultado = orq.mensaje_donante(conv.id, r)
    assert resultado.donacion is not None, orq.db.get(type(conv), conv.id).mensajes[-1].texto
    return resultado.donacion


def oferta_pendiente(db, donacion) -> Oferta:
    return db.scalar(select(Oferta).where(Oferta.donacion_id == donacion.id, Oferta.estado == EstadoOferta.PENDIENTE))


def recoleccion_propuesta(db, donacion) -> Recoleccion:
    return db.scalar(select(Recoleccion).where(
        Recoleccion.donacion_id == donacion.id, Recoleccion.estado == EstadoRecoleccion.PROPUESTA))


def mensajes(db, donacion):
    return db.get(Conversacion, donacion.conversacion_id).mensajes


def agentes_en_bitacora(db, donacion) -> set[str]:
    return {e.agente for e in db.scalars(select(EventoAgente).where(EventoAgente.donacion_id == donacion.id))}


PAN = "Tengo 25 kg de pan dulce del día, pueden pasar a las 6 pm"


class TestRescateFeliz:
    def test_de_la_conversacion_al_impacto(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        assert d.estado == EstadoDonacion.OFRECIDA

        oferta = oferta_pendiente(db, d)
        orq.responder_oferta(oferta.id, aceptar=True)
        assert d.estado == EstadoDonacion.ASIGNADA and d.receptor_id == oferta.receptor_id

        rec = recoleccion_propuesta(db, d)
        orq.responder_recoleccion(rec.id, aceptar=True)
        assert d.estado == EstadoDonacion.EN_RECOLECCION
        orq.avanzar_recoleccion(rec.id, "recogida")
        assert d.estado == EstadoDonacion.EN_CAMINO
        orq.avanzar_recoleccion(rec.id, "entregada")
        assert d.estado == EstadoDonacion.ENTREGADA

        orq.confirmar_recepcion(d.id)
        assert d.estado == EstadoDonacion.COMPLETADA and d.completada_en == reloj.ahora()
        impacto = db.scalar(select(RegistroImpacto).where(RegistroImpacto.donacion_id == d.id))
        assert (impacto.kg, impacto.raciones, impacto.personas) == (25.0, 50.0, 16.7)

    def test_los_cuatro_agentes_y_el_orquestador_dejan_huella(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        rec = recoleccion_propuesta(db, d)
        orq.responder_recoleccion(rec.id, True)
        orq.avanzar_recoleccion(rec.id, "recogida")
        orq.avanzar_recoleccion(rec.id, "entregada")
        orq.confirmar_recepcion(d.id)
        assert agentes_en_bitacora(db, d) == {"captador", "orquestador", "coordinador", "logistico", "impacto"}

    def test_el_donante_recibe_avisos_de_cada_agente_en_su_chat(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        rec = recoleccion_propuesta(db, d)
        orq.responder_recoleccion(rec.id, True)
        orq.avanzar_recoleccion(rec.id, "recogida")
        orq.avanzar_recoleccion(rec.id, "entregada")
        orq.confirmar_recepcion(d.id)
        chat = mensajes(db, d)
        roles = {m.rol for m in chat}
        assert {"captador", "coordinador", "logistico", "impacto", "donante"} <= roles
        assert "Rescate completado" in chat[-1].texto

    def test_kpis_de_proceso_de_un_rescate_aceptado_a_la_primera(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        kpis = orq.impacto.resumen()["kpis"]
        assert kpis["donaciones_reales"] == 1 and kpis["aceptacion_primera_oferta"] == 1.0
        assert kpis["segundos_primera_oferta_mediana"] == 0  # el reloj está congelado

    def test_el_receptor_puede_confirmar_otra_cantidad(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        rec = recoleccion_propuesta(db, d)
        orq.responder_recoleccion(rec.id, True)
        orq.avanzar_recoleccion(rec.id, "recogida")
        orq.avanzar_recoleccion(rec.id, "entregada")
        orq.confirmar_recepcion(d.id, kg_recibidos=20)
        assert db.scalar(select(RegistroImpacto.kg)) == 20.0


class TestRechazoYReasignacion:
    def test_un_rechazo_reasigna_a_otro_receptor_y_avisa_al_donante(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        primera = oferta_pendiente(db, d)
        orq.responder_oferta(primera.id, aceptar=False, motivo="Sin espacio hoy")
        segunda = oferta_pendiente(db, d)
        assert segunda is not None and segunda.receptor_id != primera.receptor_id
        assert d.estado == EstadoDonacion.OFRECIDA
        conv_msgs = [m.texto for m in mensajes(db, d)]
        assert any("no pudo recibirla" in t for t in conv_msgs)

    def test_oferta_sin_respuesta_se_reasigna_al_pasar_el_tiempo(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        primera = oferta_pendiente(db, d)
        reloj.avanzar(16)
        orq.tick()
        assert primera.estado == EstadoOferta.EXPIRADA
        segunda = oferta_pendiente(db, d)
        assert segunda is not None and segunda.receptor_id != primera.receptor_id

    def test_voluntario_que_rechaza_se_reemplaza(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        primera = recoleccion_propuesta(db, d)
        orq.responder_recoleccion(primera.id, aceptar=False, motivo="Ya no puedo")
        segunda = recoleccion_propuesta(db, d)
        assert segunda is not None and segunda.voluntario_id != primera.voluntario_id

    def test_si_todos_los_receptores_rechazan_la_donacion_queda_sin_receptor(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        while (oferta := oferta_pendiente(db, d)) is not None:
            orq.responder_oferta(oferta.id, aceptar=False)
        assert d.estado == EstadoDonacion.SIN_RECEPTOR

    def test_reintento_del_administrador_tras_verificar_a_un_receptor(self, db, orq):
        for r in db.scalars(select(Receptor)):
            r.verificado = False
        db.commit()
        d = donar(orq, PAN, 1, "sí")
        assert d.estado == EstadoDonacion.SIN_RECEPTOR
        orq.verificar_receptor(1)
        orq.reintentar(d.id)
        assert d.estado == EstadoDonacion.OFRECIDA and oferta_pendiente(db, d).receptor_id == 1

    def test_sin_voluntarios_se_puede_reintentar(self, db, orq):
        for v in db.scalars(select(Voluntario)):
            v.disponible = False
        db.commit()
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        assert d.estado == EstadoDonacion.SIN_VOLUNTARIO
        for v in db.scalars(select(Voluntario)):
            v.disponible = True
        orq.reintentar(d.id)
        assert recoleccion_propuesta(db, d) is not None
        assert d.estado == EstadoDonacion.ASIGNADA  # ya no figura como "sin voluntario"


class TestSupervisionHumana:
    POLLO = ("Tengo 12 kg de pollo, vence mañana", 10, "sí", "sí")  # cadena de frío, confirmar

    def test_alimento_de_riesgo_espera_aprobacion_antes_de_asignarse(self, db, orq):
        texto, donante, *resp = self.POLLO
        d = donar(orq, texto, donante, *resp)
        assert d.estado == EstadoDonacion.PENDIENTE_VALIDACION
        assert oferta_pendiente(db, d) is None  # nadie recibe ofertas sin revisión

    def test_aprobar_lo_manda_al_coordinador_con_receptor_que_tenga_frio(self, db, orq):
        texto, donante, *resp = self.POLLO
        d = donar(orq, texto, donante, *resp)
        orq.revision_humana(d.id, aprobar=True, nota="Se ve bien, viene en hielera")
        oferta = oferta_pendiente(db, d)
        assert d.estado == EstadoDonacion.OFRECIDA
        assert oferta.receptor.capacidad_frio_kg > 0
        assert "humano" in agentes_en_bitacora(db, d)

    def test_rechazar_cierra_la_donacion_y_avisa_al_donante(self, db, orq):
        texto, donante, *resp = self.POLLO
        d = donar(orq, texto, donante, *resp)
        orq.revision_humana(d.id, aprobar=False, nota="Sin evidencia de cadena de frío")
        assert d.estado == EstadoDonacion.RECHAZADA and oferta_pendiente(db, d) is None
        msgs = mensajes(db, d)
        assert "no pudimos aceptarla" in msgs[-1].texto

    def test_la_aprobacion_tardia_reabre_la_ventana_de_recoleccion(self, db, orq):
        texto, donante, *resp = self.POLLO
        d = donar(orq, texto, donante, *resp)
        reloj.avanzar(90)  # la revisión tardó una hora y media
        orq.revision_humana(d.id, aprobar=True)
        assert d.recoleccion_desde >= reloj.ahora() and d.recoleccion_hasta > d.recoleccion_desde

    def test_un_receptor_nuevo_nace_sin_verificar(self, db, orq):
        r = orq.registrar_receptor(nombre="Comedor Nuevo", tipo="comedor", direccion="x", municipio="Zapopan",
                                   lat=20.7, lon=-103.4, capacidad_diaria_kg=50, necesidades={"pan": 3})
        assert r.verificado is False
        assert orq.verificar_receptor(r.id).verificado is True


class TestCaducidadYTransicionesInvalidas:
    def test_donacion_que_caduca_cancela_todo_y_avisa(self, db, orq):
        d = donar(orq, "Tengo 25 kg de pan, caduca en 1 hora", 1, "sí")
        assert oferta_pendiente(db, d) is not None
        reloj.avanzar(61)
        orq.tick()
        assert d.estado == EstadoDonacion.CADUCADA
        assert oferta_pendiente(db, d) is None
        msgs = mensajes(db, d)
        assert "caducó" in msgs[-1].texto

    def test_no_se_puede_confirmar_algo_que_no_se_ha_entregado(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        with pytest.raises(ValueError, match="aún no ha sido entregada"):
            orq.confirmar_recepcion(d.id)

    def test_no_se_responde_dos_veces_la_misma_oferta(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        oferta = oferta_pendiente(db, d)
        orq.responder_oferta(oferta.id, True)
        with pytest.raises(ValueError):
            orq.responder_oferta(oferta.id, False)

    def test_revision_solo_aplica_a_donaciones_pendientes(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        with pytest.raises(ValueError):
            orq.revision_humana(d.id, aprobar=True)

    def test_estado_invalido_del_voluntario(self, db, orq):
        d = donar(orq, PAN, 1, "sí")
        orq.responder_oferta(oferta_pendiente(db, d).id, True)
        rec = recoleccion_propuesta(db, d)
        with pytest.raises(ValueError):
            orq.avanzar_recoleccion(rec.id, "volando")

    def test_entidades_inexistentes(self, orq):
        for llamada in (lambda: orq.iniciar_conversacion(999), lambda: orq.responder_oferta(999, True),
                        lambda: orq.confirmar_recepcion(999), lambda: orq.verificar_receptor(999)):
            with pytest.raises(LookupError):
                llamada()
