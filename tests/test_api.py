"""Pruebas de la API HTTP: el mismo recorrido que hace la interfaz web, con TestClient.

Hora de las pruebas: martes 10 de noviembre de 2026, 17:30 (reloj congelado).
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from comparte.db import crear_motor
from comparte.llm import ExtractorReglas
from comparte.main import crear_app

PAN = "Tengo 25 kg de pan dulce del día, pueden pasar a las 6 pm"


@pytest.fixture
def cliente(ajustes_prueba):
    app = crear_app(ajustes_prueba, motor=crear_motor("sqlite://"), extractor=ExtractorReglas(),
                    con_historial=False, servir_web=False)
    with TestClient(app) as c:
        yield c


def donar(cliente, texto=PAN, donante_id=1, *respuestas, imagen=None):
    conv = cliente.post("/api/conversaciones", json={"donante_id": donante_id}).json()
    cuerpo = {"texto": texto, **(imagen or {})}
    r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json=cuerpo).json()
    for texto_extra in respuestas or ("sí",):
        r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json={"texto": texto_extra}).json()
    return conv["id"], r


def oferta_del_receptor(cliente, receptor_id):
    return cliente.get(f"/api/receptores/{receptor_id}/tareas").json()["ofertas"][0]


class TestCatalogos:
    def test_estado(self, cliente):
        e = cliente.get("/api/estado").json()
        assert e["motor_lenguaje"] == "reglas" and e["hora"] == "2026-11-10T17:30:00"

    def test_actores_del_piloto(self, cliente):
        assert len(cliente.get("/api/donantes").json()) == 10
        assert len(cliente.get("/api/receptores").json()) == 6
        assert len(cliente.get("/api/voluntarios").json()) == 6

    def test_documentacion_openapi_disponible(self, cliente):
        assert cliente.get("/openapi.json").status_code == 200


class TestRecorridoCompleto:
    def test_de_la_conversacion_al_reporte_del_donante(self, cliente):
        conv_id, r = donar(cliente)
        d = r["donacion"]
        assert d["estado"] == "ofrecida" and d["total_kg"] == 25.0 and r["bloqueada"] is False
        roles = [m["rol"] for m in r["conversacion"]["mensajes"]]
        assert roles[0] == "captador" and "coordinador" in roles

        # el receptor ve la oferta y la acepta
        detalle = cliente.get(f"/api/donaciones/{d['id']}").json()
        receptor_id = detalle["ofertas"][0]["receptor"]["id"]
        assert detalle["evaluacion"]["candidatos"][0]["receptor_id"] == receptor_id  # ranking explicable
        oferta = oferta_del_receptor(cliente, receptor_id)
        assert oferta["donacion"]["id"] == d["id"] and oferta["justificacion"]
        assert cliente.post(f"/api/ofertas/{oferta['id']}/respuesta", json={"aceptar": True}).status_code == 200

        # el voluntario ve la propuesta y completa la entrega
        rec = detalle_recoleccion(cliente, d["id"])
        vol_id = rec["voluntario"]["id"]
        propuesta = cliente.get(f"/api/voluntarios/{vol_id}/tareas").json()["propuestas"][0]
        assert propuesta["donacion"]["receptor"]["id"] == receptor_id and propuesta["ruta"]["puntos"]
        assert cliente.post(f"/api/recolecciones/{rec['id']}/respuesta", json={"aceptar": True}).status_code == 200
        assert cliente.get(f"/api/voluntarios/{vol_id}/tareas").json()["activas"][0]["id"] == rec["id"]
        for estado in ("recogida", "entregada"):
            assert cliente.post(f"/api/recolecciones/{rec['id']}/avance", json={"estado": estado}).status_code == 200

        # el receptor confirma y el impacto aparece
        por_confirmar = cliente.get(f"/api/receptores/{receptor_id}/tareas").json()["por_confirmar"]
        assert [x["id"] for x in por_confirmar] == [d["id"]]
        final = cliente.post(f"/api/donaciones/{d['id']}/confirmacion-recepcion", json={}).json()
        assert final["estado"] == "completada"
        assert {e["agente"] for e in final["eventos"]} >= {"captador", "orquestador", "coordinador", "logistico", "impacto"}

        impacto = cliente.get("/api/impacto").json()
        assert impacto["totales"]["kg"] == 25.0 and impacto["totales"]["raciones"] == 50.0
        assert cliente.get("/api/impacto?simuladas=false").json()["kpis"]["completadas_reales"] == 1
        reporte = cliente.get("/api/impacto/donantes/1").json()
        assert reporte["rescates"][0]["donacion_id"] == d["id"]

        chat = cliente.get(f"/api/conversaciones/{conv_id}").json()["mensajes"]
        assert "Rescate completado" in chat[-1]["texto"]
        assert cliente.get("/api/eventos?limite=5").json()[0]["agente"] == "impacto"

    def test_la_lista_de_donaciones_oculta_las_simuladas(self, cliente):
        donar(cliente)
        assert [x["estado"] for x in cliente.get("/api/donaciones").json()] == ["ofrecida"]
        assert cliente.get("/api/donaciones?estado=completada").json() == []


def detalle_recoleccion(cliente, donacion_id):
    return cliente.get(f"/api/donaciones/{donacion_id}").json()["recolecciones"][0]


class TestErrores:
    def test_entidad_inexistente_es_404(self, cliente):
        assert cliente.get("/api/donaciones/999").status_code == 404
        assert cliente.post("/api/conversaciones", json={"donante_id": 999}).status_code == 404
        assert cliente.get("/api/receptores/999/tareas").status_code == 404
        assert cliente.get("/api/impacto/donantes/999").status_code == 404

    def test_responder_dos_veces_es_409(self, cliente):
        _, r = donar(cliente)
        oferta = oferta_del_receptor(cliente, cliente.get(f"/api/donaciones/{r['donacion']['id']}").json()["ofertas"][0]["receptor"]["id"])
        assert cliente.post(f"/api/ofertas/{oferta['id']}/respuesta", json={"aceptar": True}).status_code == 200
        segunda = cliente.post(f"/api/ofertas/{oferta['id']}/respuesta", json={"aceptar": False})
        assert segunda.status_code == 409 and "detail" in segunda.json()

    def test_confirmar_antes_de_la_entrega_es_409(self, cliente):
        _, r = donar(cliente)
        assert cliente.post(f"/api/donaciones/{r['donacion']['id']}/confirmacion-recepcion", json={}).status_code == 409

    def test_validacion_de_cuerpos_es_422(self, cliente):
        conv = cliente.post("/api/conversaciones", json={"donante_id": 1}).json()
        assert cliente.post(f"/api/conversaciones/{conv['id']}/mensajes", json={"texto": ""}).status_code == 422
        assert cliente.post("/api/recolecciones/1/avance", json={"estado": "volando"}).status_code == 422
        assert cliente.post("/api/demo/fijar-hora", json={"hora": "25:99"}).status_code == 422
        assert cliente.post("/api/receptores", json={"nombre": "X", "municipio": "Zapopan", "lat": 200, "lon": 0}).status_code == 422


class TestFotos:
    def test_foto_valida_se_guarda_y_se_sirve_su_url(self, cliente):
        foto = {"imagen_base64": base64.b64encode(b"\x89PNG-falso").decode(), "imagen_tipo": "image/png"}
        conv_id, r = donar(cliente, "20 kg de pan", 1, "sí", imagen=foto)
        mensajes = cliente.get(f"/api/conversaciones/{conv_id}").json()["mensajes"]
        con_foto = [m for m in mensajes if m["imagen"]]
        assert con_foto and con_foto[0]["imagen"].startswith("/uploads/")
        assert r["donacion"]["foto"] == con_foto[0]["imagen"]

    def test_base64_invalido_es_400(self, cliente):
        conv = cliente.post("/api/conversaciones", json={"donante_id": 1}).json()
        r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes",
                         json={"texto": "foto", "imagen_base64": "###", "imagen_tipo": "image/png"})
        assert r.status_code == 400

    def test_foto_sin_tipo_es_400(self, cliente):
        conv = cliente.post("/api/conversaciones", json={"donante_id": 1}).json()
        r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes",
                         json={"texto": "foto", "imagen_base64": base64.b64encode(b"x").decode()})
        assert r.status_code == 400

    def test_tipo_no_permitido_es_422(self, cliente):
        conv = cliente.post("/api/conversaciones", json={"donante_id": 1}).json()
        r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes",
                         json={"texto": "x", "imagen_base64": base64.b64encode(b"x").decode(), "imagen_tipo": "application/pdf"})
        assert r.status_code == 422

    def test_foto_de_mas_de_5_mb_es_413(self, cliente):
        conv = cliente.post("/api/conversaciones", json={"donante_id": 1}).json()
        grande = base64.b64encode(b"0" * (5 * 1024 * 1024 + 1)).decode()
        r = cliente.post(f"/api/conversaciones/{conv['id']}/mensajes",
                         json={"texto": "foto", "imagen_base64": grande, "imagen_tipo": "image/jpeg"})
        assert r.status_code == 413


class TestAdministracion:
    POLLO = ("Tengo 12 kg de pollo, vence mañana", 10, "sí", "sí")

    def test_cola_de_validacion_aprobar_y_rechazar(self, cliente):
        texto, donante, *resp = self.POLLO
        _, r = donar(cliente, texto, donante, *resp)
        d = r["donacion"]
        assert d["estado"] == "pendiente_validacion"
        cola = cliente.get("/api/admin/pendientes").json()["validacion"]
        assert [x["id"] for x in cola] == [d["id"]] and cola[0]["inocuidad"]["motivos"]

        aprobada = cliente.post(f"/api/donaciones/{d['id']}/revision", json={"aprobar": True, "nota": "ok"}).json()
        assert aprobada["estado"] == "ofrecida"
        assert cliente.post(f"/api/donaciones/{d['id']}/revision", json={"aprobar": True}).status_code == 409

    def test_receptor_nuevo_nace_sin_verificar_y_se_valida(self, cliente):
        nuevo = {"nombre": "Comedor Nuevo", "municipio": "Zapopan", "lat": 20.7, "lon": -103.4,
                 "capacidad_diaria_kg": 50, "necesidades": {"pan": 3}}
        creado = cliente.post("/api/receptores", json=nuevo)
        assert creado.status_code == 201 and creado.json()["verificado"] is False
        sin_verificar = cliente.get("/api/admin/pendientes").json()["receptores_sin_verificar"]
        assert creado.json()["id"] in [x["id"] for x in sin_verificar]
        ok = cliente.post(f"/api/receptores/{creado.json()['id']}/verificacion", json={"verificado": True})
        assert ok.json()["verificado"] is True

    def test_reintento_de_donacion_atorada(self, cliente):
        for r in cliente.get("/api/receptores").json():
            cliente.post(f"/api/receptores/{r['id']}/verificacion", json={"verificado": False})
        _, resp = donar(cliente)
        d = resp["donacion"]
        assert d["estado"] == "sin_receptor"
        assert [x["id"] for x in cliente.get("/api/admin/pendientes").json()["atoradas"]] == [d["id"]]
        cliente.post("/api/receptores/1/verificacion", json={"verificado": True})
        assert cliente.post(f"/api/donaciones/{d['id']}/reintento").json()["estado"] == "ofrecida"


class TestControlesDeDemo:
    def test_avanzar_el_reloj_expira_la_oferta_y_la_reasigna(self, cliente):
        _, r = donar(cliente)
        d_id = r["donacion"]["id"]
        primera = cliente.get(f"/api/donaciones/{d_id}").json()["ofertas"][0]
        hora = cliente.post("/api/demo/avanzar-reloj", json={"minutos": 16}).json()["hora"]
        assert hora == "2026-11-10T17:46:00"
        ofertas = cliente.get(f"/api/donaciones/{d_id}").json()["ofertas"]
        assert [o["estado"] for o in ofertas] == ["expirada", "pendiente"]
        assert ofertas[1]["receptor"]["id"] != primera["receptor"]["id"]

    def test_fijar_hora(self, cliente):
        assert cliente.post("/api/demo/fijar-hora", json={"hora": "16:00"}).json()["hora"].endswith("16:00:00")

    def test_reiniciar_borra_donaciones_y_recarga_el_piloto(self, cliente):
        donar(cliente)
        assert cliente.get("/api/donaciones").json()
        conteos = cliente.post("/api/demo/reiniciar", json={"con_historial": True}).json()
        assert conteos["donantes"] == 10 and conteos["historial"] == 40
        assert cliente.get("/api/donaciones").json() == []
        assert cliente.get("/api/impacto").json()["totales"]["rescates"] == 40
