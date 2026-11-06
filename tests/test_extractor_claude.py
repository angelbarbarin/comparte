"""Pruebas del motor Claude **con un cliente simulado** (no usan red ni clave de API).

Verifican la construcción de la petición, la conversión de la respuesta y el respaldo ante fallos.
No sustituyen una prueba contra la API real (ver el aviso en ``comparte/llm/claude.py``).
"""

from __future__ import annotations

import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from comparte.config import Ajustes, obtener_ajustes
from comparte.llm import ExtractorReglas, crear_extractor
from comparte.llm.claude import ESQUEMA, ExtractorClaude, ExtractorConRespaldo, a_extraccion

AHORA = datetime(2026, 11, 10, 17, 30)

RESPUESTA_OK = {
    "intencion": "donar",
    "items": [
        {"nombre": "pan dulce", "cantidad": 25, "unidad": "kilos"},
        {"nombre": "fruta madura", "cantidad": None, "unidad": None},
    ],
    "caduca_en": "2026-11-10T23:59",
    "recoleccion_desde": "2026-11-10T20:00:00-06:00",  # con zona: debe convertirse a hora local
    "recoleccion_hasta": None,
    "condiciones": ["empacado", "inventada"],
    "notas": None,
}


class ClienteFalso:
    """Imita ``anthropic.Anthropic`` lo justo: ``cliente.messages.create(...)``."""

    def __init__(self, contenido: str | Exception, stop_reason: str = "end_turn"):
        self.llamadas: list[dict] = []
        self._contenido = contenido
        self._stop = stop_reason
        self.messages = SimpleNamespace(create=self._crear)

    def _crear(self, **kwargs):
        self.llamadas.append(kwargs)
        if isinstance(self._contenido, Exception):
            raise self._contenido
        bloques = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self._contenido)]
        return SimpleNamespace(content=bloques, stop_reason=self._stop)


def test_convierte_la_respuesta_estructurada():
    ext = a_extraccion(RESPUESTA_OK)
    assert ext.intencion == "donar"
    assert [(i.nombre, i.cantidad, i.unidad) for i in ext.items] == [
        ("pan dulce", 25.0, "kg"), ("fruta madura", None, None)]
    assert ext.caduca_en == datetime(2026, 11, 10, 23, 59)
    assert ext.recoleccion_desde == datetime(2026, 11, 10, 20, 0)
    assert ext.condiciones == ["empacado"]  # las etiquetas inventadas se descartan


def test_fecha_invalida_se_ignora():
    assert a_extraccion({"intencion": "donar", "caduca_en": "mañana"}).caduca_en is None


def test_intencion_desconocida_es_otro():
    assert a_extraccion({"intencion": "bailar"}).intencion == "otro"


def test_la_peticion_pide_salida_estructurada_sin_forzar_herramientas():
    cliente = ClienteFalso(json.dumps(RESPUESTA_OK))
    ExtractorClaude(cliente=cliente, modelo="claude-opus-5-5").extraer("tengo pan", {}, AHORA)
    peticion = cliente.llamadas[0]
    assert peticion["model"] == "claude-opus-5-5"
    assert peticion["output_config"]["format"] == {"type": "json_schema", "schema": ESQUEMA}
    assert peticion["output_config"]["effort"] == "low"
    assert "tool_choice" not in peticion  # los modelos nuevos rechazan tool_choice forzado
    texto = peticion["messages"][0]["content"][-1]["text"]
    assert "2026-11-10T17:30" in texto and "martes" in texto and "tengo pan" in texto


def test_la_foto_se_envia_como_bloque_de_imagen_base64():
    cliente = ClienteFalso(json.dumps(RESPUESTA_OK))
    ExtractorClaude(cliente=cliente).extraer("mira", {}, AHORA, imagen=(b"\x89PNGdatos", "image/png"))
    bloques = cliente.llamadas[0]["messages"][0]["content"]
    assert bloques[0]["type"] == "image"
    assert bloques[0]["source"]["media_type"] == "image/png"
    assert bloques[0]["source"]["type"] == "base64" and bloques[0]["source"]["data"]
    assert bloques[1]["type"] == "text"


def test_el_borrador_y_la_pregunta_pendiente_viajan_en_el_mensaje():
    cliente = ClienteFalso(json.dumps(RESPUESTA_OK))
    borrador = {"items": [{"nombre": "pan", "cantidad": None, "unidad": None}], "pendiente": "cantidad"}
    ExtractorClaude(cliente=cliente).extraer("20 kg", borrador, AHORA)
    texto = cliente.llamadas[0]["messages"][0]["content"][-1]["text"]
    assert '"pregunta_pendiente": "cantidad"' in texto and '"nombre": "pan"' in texto


@pytest.mark.parametrize("falla", [
    RuntimeError("sin red"),
    "esto no es json",
])
def test_si_claude_falla_se_usa_el_motor_de_reglas(falla):
    principal = ExtractorClaude(cliente=ClienteFalso(falla))
    extractor = ExtractorConRespaldo(principal, ExtractorReglas())
    ext = extractor.extraer("Tengo 25 kg de pan", {}, AHORA)
    assert [(i.nombre, i.cantidad) for i in ext.items] == [("pan", 25.0)]
    assert extractor.ultimo_error


def test_refusal_cuenta_como_fallo():
    principal = ExtractorClaude(cliente=ClienteFalso("{}", stop_reason="refusal"))
    with pytest.raises(RuntimeError):
        principal.extraer("x", {}, AHORA)


def _ajustes(**cambios) -> Ajustes:
    base = obtener_ajustes()
    return Ajustes(**{**base.__dict__, **cambios})


class TestFabrica:
    def test_reglas_explicito(self):
        assert crear_extractor(_ajustes(modo_llm="reglas", api_key="x")).nombre == "reglas"

    def test_auto_sin_clave_usa_reglas(self):
        assert crear_extractor(_ajustes(modo_llm="auto", api_key=None)).nombre == "reglas"

    def test_auto_con_clave_usa_claude_con_respaldo(self):
        assert crear_extractor(_ajustes(modo_llm="auto", api_key="sk-prueba")).nombre == "claude+reglas"

    def test_claude_sin_clave_falla_con_mensaje_claro(self):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            crear_extractor(_ajustes(modo_llm="claude", api_key=None))

    def test_modo_invalido(self):
        with pytest.raises(ValueError):
            crear_extractor(_ajustes(modo_llm="gpt"))
