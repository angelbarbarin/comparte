"""Pruebas del Agente Captador: conversación completa con el motor de reglas.

Hora de las pruebas: martes 10 de noviembre de 2026, 17:30 (ver conftest).
"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from comparte import reloj
from comparte.agentes.captador import AgenteCaptador
from comparte.datos_demo import sembrar_actores
from comparte.llm import ExtractorReglas
from comparte.modelos import Conversacion, Donacion, Donante, EstadoDonacion, EventoAgente


@pytest.fixture
def captador(db, tmp_path):
    sembrar_actores(db)
    return AgenteCaptador(db, ExtractorReglas(), carpeta_datos=tmp_path)


@pytest.fixture
def conv(db, captador) -> Conversacion:
    c = captador.iniciar_conversacion(db.get(Donante, 1))  # Panadería La Espiga
    db.commit()
    return c


def decir(db, captador, conv, texto, imagen=None):
    resultado = captador.procesar_mensaje(conv, texto, imagen)
    db.commit()
    return resultado


def ultimo(conv) -> str:
    return conv.mensajes[-1].texto


def acciones(db, **filtros) -> list[str]:
    return [e.accion for e in db.scalars(select(EventoAgente).filter_by(**filtros).order_by(EventoAgente.id))]


def test_saluda_al_donante_por_su_nombre(conv):
    assert conv.mensajes[0].rol == "captador"
    assert "Rosa" in conv.mensajes[0].texto


class TestRegistroFeliz:
    def test_describir_y_confirmar_en_dos_mensajes(self, db, captador, conv):
        decir(db, captador, conv,
              "Tengo 25 kg de pan dulce del día y 10 kg de fruta madura, pueden pasar después de las 8 pm")
        resumen = ultimo(conv)
        assert "Esto es lo que entendí" in resumen
        assert "25 kg de pan dulce" in resumen and "10 kg de fruta" in resumen
        assert "Total: 35 kg" in resumen
        assert "Caduca: hoy 23:59" in resumen and "(estimado)" not in resumen.split("Caduca:")[1].split("\n")[0]
        assert "Recolección: hoy 20:00 a 23:00" in resumen
        assert db.scalar(select(Donacion.id)) is None  # aún no se registra: falta confirmar

        resultado = decir(db, captador, conv, "sí")
        d = resultado.donacion
        assert d is not None and d.estado == EstadoDonacion.REGISTRADA
        assert d.total_kg == 35.0 and len(d.items) == 2
        assert d.caduca_en == datetime(2026, 11, 10, 23, 59)
        assert d.recoleccion_desde == datetime(2026, 11, 10, 20, 0)
        assert d.recoleccion_hasta == datetime(2026, 11, 10, 23, 0)  # +3 h por defecto
        assert d.categoria_principal == "pan" and d.requiere_frio is False
        assert conv.donacion_id == d.id and conv.borrador == {}
        assert acciones(db, donacion_id=d.id) == ["donacion_registrada", "inocuidad_evaluada"]

    def test_mide_los_segundos_que_tomo_registrar(self, db, captador, conv):
        decir(db, captador, conv, "20 kg de pan")
        reloj.avanzar(0.5)  # 30 s después
        d = decir(db, captador, conv, "sí").donacion
        assert d.segundos_registro == 30

    def test_se_puede_registrar_una_segunda_donacion_en_la_misma_conversacion(self, db, captador, conv):
        decir(db, captador, conv, "20 kg de pan")
        primera = decir(db, captador, conv, "sí").donacion
        decir(db, captador, conv, "5 kg de jitomate")
        segunda = decir(db, captador, conv, "sí").donacion
        assert segunda.id != primera.id and conv.donacion_id == segunda.id


class TestPreguntasYSuposiciones:
    def test_pregunta_la_cantidad_si_falta(self, db, captador, conv):
        decir(db, captador, conv, "Tengo pan dulce")
        assert "¿Cuánto pan dulce tienes?" in ultimo(conv)
        decir(db, captador, conv, "20 kg")
        assert "20 kg de pan dulce" in ultimo(conv)

    def test_caducidad_estimada_se_marca_en_el_resumen(self, db, captador, conv):
        decir(db, captador, conv, "20 kg de pan")
        assert "Caduca: mañana 17:30 (estimado)" in ultimo(conv)  # el pan dura 24 h por defecto

    def test_pesos_en_piezas_son_estimados(self, db, captador, conv):
        decir(db, captador, conv, "me sobraron 50 bolillos")
        assert "Total: aprox. 3.5 kg" in ultimo(conv)
        assert "peso estimado" in ultimo(conv)

    def test_corregir_la_cantidad_mientras_se_confirma(self, db, captador, conv):
        decir(db, captador, conv, "25 kg de pan")
        decir(db, captador, conv, "son 30 kg")
        assert "30 kg de pan" in ultimo(conv) and "Esto es lo que entendí" in ultimo(conv)
        assert decir(db, captador, conv, "sí").donacion.total_kg == 30.0

    def test_decir_no_al_resumen_pregunta_que_corregir(self, db, captador, conv):
        decir(db, captador, conv, "25 kg de pan")
        decir(db, captador, conv, "no")
        assert "¿Qué quieres corregir?" in ultimo(conv)
        decir(db, captador, conv, "caduca mañana")
        assert "Caduca: mañana 23:59" in ultimo(conv)

    def test_cancelar_borra_el_borrador(self, db, captador, conv):
        decir(db, captador, conv, "25 kg de pan")
        decir(db, captador, conv, "mejor no")
        assert conv.borrador == {} and "cancelé" in ultimo(conv)
        assert db.scalar(select(Donacion.id)) is None

    def test_un_saludo_recibe_orientacion(self, db, captador, conv):
        decir(db, captador, conv, "hola, buenas tardes")
        assert "Cuéntame qué alimento" in ultimo(conv)

    def test_dos_alimentos_con_la_misma_categoria_no_se_pisan(self, db, captador, conv):
        decir(db, captador, conv, "10 kg de manzana y 5 kg de naranja")
        d = decir(db, captador, conv, "sí").donacion
        assert sorted((i["nombre"], i["kg"]) for i in d.items) == [("manzana", 10.0), ("naranja", 5.0)]


class TestInocuidadEnLaConversacion:
    def test_alimento_refrigerado_pregunta_por_la_cadena_de_frio(self, db, captador, conv):
        decir(db, captador, conv, "12 kg de pollo")
        assert "cadena de frío" in ultimo(conv)
        decir(db, captador, conv, "sí")
        assert "una persona del equipo lo revisará" in ultimo(conv)
        d = decir(db, captador, conv, "sí").donacion
        assert d.inocuidad["requiere_revision"] is True and d.requiere_frio is True
        assert d.inocuidad["nivel"] == "alto"

    def test_la_pregunta_de_frio_concuerda_en_numero_con_varios_alimentos(self, db, captador, conv):
        decir(db, captador, conv, "Tengo 12 kg de pollo y 8 litros de leche")
        assert "Pollo y leche necesitan cadena de frío" in ultimo(conv)

    def test_cadena_de_frio_rota_bloquea(self, db, captador, conv):
        decir(db, captador, conv, "12 kg de pollo")
        resultado = decir(db, captador, conv, "no")
        assert resultado.bloqueada and resultado.donacion is None
        assert "No puedo registrar" in ultimo(conv) and "cadena de frío" in ultimo(conv)
        assert "donacion_bloqueada" in acciones(db, conversacion_id=conv.id)

    def test_no_acepta_alcohol(self, db, captador, conv):
        resultado = decir(db, captador, conv, "tengo 10 litros de cerveza")
        assert resultado.bloqueada and "cerveza" in ultimo(conv)

    def test_no_acepta_producto_ya_caducado(self, db, captador, conv):
        resultado = decir(db, captador, conv, "20 kg de pan, caduca hoy a las 3 pm")
        assert resultado.bloqueada and "caducado" in ultimo(conv)

    def test_no_acepta_alimento_en_mal_estado(self, db, captador, conv):
        resultado = decir(db, captador, conv, "15 kg de papa que ya tiene moho")
        assert resultado.bloqueada

    def test_alimento_desconocido_va_a_revision(self, db, captador, conv):
        decir(db, captador, conv, "5 kg de sushi")
        d = decir(db, captador, conv, "sí").donacion
        assert d.items[0]["clave"] == "desconocido"
        assert d.inocuidad["requiere_revision"] is True


class TestFotos:
    def test_la_foto_se_guarda_y_queda_ligada_a_la_donacion(self, db, captador, conv, tmp_path):
        decir(db, captador, conv, "20 kg de pan", imagen=(b"datos-de-imagen", "image/png"))
        d = decir(db, captador, conv, "sí").donacion
        assert d.foto and d.foto.startswith("uploads/")
        assert (tmp_path / d.foto).read_bytes() == b"datos-de-imagen"
        assert conv.mensajes[1].imagen == d.foto

    def test_foto_sin_texto_util_con_motor_de_reglas_pide_el_dato(self, db, captador, conv):
        decir(db, captador, conv, "mira lo que sobró", imagen=(b"x", "image/jpeg"))
        assert "no puedo leerla" in ultimo(conv)
