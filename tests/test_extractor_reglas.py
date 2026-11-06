"""Pruebas del motor de lenguaje por reglas con frases como las diría un donante.

"Hoy" en estas pruebas es el martes 10 de noviembre de 2026 a las 17:30 (ver conftest).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from comparte.llm.reglas import ExtractorReglas

AHORA = datetime(2026, 11, 10, 17, 30)
HOY_FIN = datetime(2026, 11, 10, 23, 59)


def extraer(texto: str, borrador: dict | None = None):
    return ExtractorReglas().extraer(texto, borrador or {}, AHORA)


def tuplas(ext):
    return [(i.nombre, i.cantidad, i.unidad) for i in ext.items]


class TestCantidadesYAlimentos:
    def test_pan_con_kilos(self):
        ext = extraer("Tengo 25 kg de pan dulce del día")
        assert ext.intencion == "donar"
        assert tuplas(ext) == [("pan dulce", 25.0, "kg")]
        assert ext.caduca_en == HOY_FIN  # "del día" => caduca hoy

    def test_varios_alimentos_y_ventana_de_recoleccion(self):
        ext = extraer(
            "Hola, tengo 25 kg de pan dulce del día y 10 kg de fruta madura, "
            "pueden pasar después de las 8 pm"
        )
        assert tuplas(ext) == [("pan dulce", 25.0, "kg"), ("fruta", 10.0, "kg")]
        assert ext.recoleccion_desde == datetime(2026, 11, 10, 20, 0)
        assert ext.recoleccion_hasta is None

    def test_cajas_y_caducidad_mañana(self):
        ext = extraer("3 cajas de jitomate, caduca mañana")
        assert tuplas(ext) == [("jitomate", 3.0, "caja")]
        assert ext.caduca_en == datetime(2026, 11, 11, 23, 59)

    def test_alimento_fuera_del_catalogo_conserva_su_nombre(self):
        ext = extraer("Sobraron 2 charolas de gelatina")
        assert tuplas(ext) == [("gelatina", 2.0, "charola")]

    def test_kilo_y_medio(self):
        assert tuplas(extraer("un kilo y medio de queso")) == [("queso", 1.5, "kg")]

    def test_piezas(self):
        assert tuplas(extraer("50 piezas de bolillo")) == [("bolillo", 50.0, "pieza")]

    def test_media_docena(self):
        assert tuplas(extraer("media docena de huevos")) == [("huevos", 0.5, "docena")]

    def test_miles_con_coma(self):
        assert tuplas(extraer("1,500 kg de naranja")) == [("naranja", 1500.0, "kg")]

    def test_decimal_con_coma_o_punto(self):
        assert tuplas(extraer("2,5 kg de arroz"))[0][1] == 2.5
        assert tuplas(extraer("2.5 kg de arroz"))[0][1] == 2.5

    def test_numero_con_palabra(self):
        assert tuplas(extraer("tres cajas de manzana")) == [("manzana", 3.0, "caja")]

    def test_latas_son_unidad_y_no_alimento(self):
        assert tuplas(extraer("10 latas de atún")) == [("atún", 10.0, "lata")]

    def test_conserva_acentos_del_usuario(self):
        assert tuplas(extraer("tengo 5 kg de piña"))[0][0] == "piña"

    def test_alimento_sin_cantidad(self):
        ext = extraer("25 kilos de pan y fruta")
        assert tuplas(ext) == [("pan", 25.0, "kg"), ("fruta", None, None)]

    def test_cantidad_despues_del_alimento(self):
        assert tuplas(extraer("pan dulce, 25 kg")) == [("pan dulce", 25.0, "kg")]

    def test_cantidad_suelta_sirve_para_responder_una_pregunta(self):
        ext = extraer("20 kg")
        assert ext.intencion == "donar"
        assert tuplas(ext) == [(None, 20.0, "kg")]

    def test_numero_pegado_al_alimento_sin_unidad_son_piezas(self):
        assert tuplas(extraer("me sobraron como 40 bolillos")) == [("bolillos", 40.0, "pieza")]
        assert tuplas(extraer("tengo dos pizzas")) == [("pizzas", 2.0, "pieza")]

    def test_frase_completa_de_panaderia(self):
        ext = extraer(
            "Buenas, me sobraron 40 bolillos y 3 charolas de pan dulce, caduca hoy, pasen a las 7 pm"
        )
        assert tuplas(ext) == [("bolillos", 40.0, "pieza"), ("pan dulce", 3.0, "charola")]
        assert ext.caduca_en == HOY_FIN  # la hora de recolección NO es la caducidad
        assert ext.recoleccion_desde == datetime(2026, 11, 10, 19, 0)

    def test_un_rango_de_cantidades_no_se_confunde_con_horario(self):
        ext = extraer("de 25 a 30 kg de arroz")
        assert ext.recoleccion_desde is None and ext.recoleccion_hasta is None
        assert tuplas(ext) == [("arroz", 30.0, "kg")]


class TestFechasYHoras:
    def test_ventana_entre_las_6_y_las_8_pm(self):
        ext = extraer("pueden pasar entre las 6 y las 8 pm")
        assert ext.recoleccion_desde == datetime(2026, 11, 10, 18, 0)
        assert ext.recoleccion_hasta == datetime(2026, 11, 10, 20, 0)

    def test_ventana_de_6_a_8_pm(self):
        ext = extraer("de 6 a 8 pm")
        assert (ext.recoleccion_desde.hour, ext.recoleccion_hasta.hour) == (18, 20)

    def test_ventana_de_la_tarde_noche(self):
        ext = extraer("pueden venir de 6 a 8 de la noche")
        assert (ext.recoleccion_desde.hour, ext.recoleccion_hasta.hour) == (18, 20)

    def test_antes_de_las_9(self):
        ext = extraer("antes de las 9 pm")
        assert ext.recoleccion_hasta == datetime(2026, 11, 10, 21, 0)

    def test_a_las_7_da_una_hora_de_margen(self):
        ext = extraer("pasen a las 7")
        assert ext.recoleccion_desde == datetime(2026, 11, 10, 19, 0)
        assert ext.recoleccion_hasta == datetime(2026, 11, 10, 20, 0)

    def test_hora_en_formato_24h(self):
        assert extraer("pasen a las 20:30").recoleccion_desde == datetime(2026, 11, 10, 20, 30)

    def test_caduca_el_15_de_noviembre(self):
        assert extraer("2 kg de queso, caduca el 15 de noviembre").caduca_en == datetime(2026, 11, 15, 23, 59)

    def test_caduca_con_fecha_numerica(self):
        assert extraer("caduca 20/11").caduca_en == datetime(2026, 11, 20, 23, 59)
        assert extraer("caduca 05/12/2026").caduca_en == datetime(2026, 12, 5, 23, 59)

    def test_caduca_en_3_horas(self):
        assert extraer("caduca en 3 horas").caduca_en == datetime(2026, 11, 10, 20, 30)

    def test_caduca_en_2_dias(self):
        assert extraer("caduca en 2 días").caduca_en == datetime(2026, 11, 12, 23, 59)

    def test_caduca_el_viernes(self):
        assert extraer("vence el viernes").caduca_en == datetime(2026, 11, 13, 23, 59)

    def test_caduca_a_las_11_pm_es_hora_de_caducidad_no_de_recoleccion(self):
        ext = extraer("caduca hoy a las 11 pm")
        assert ext.caduca_en == datetime(2026, 11, 10, 23, 0)
        assert ext.recoleccion_desde is None

    def test_sin_fechas_no_inventa_nada(self):
        ext = extraer("tengo 10 kg de arroz")
        assert ext.caduca_en is None and ext.recoleccion_desde is None


class TestCondiciones:
    def test_refrigerado(self):
        assert "refrigerado" in extraer("el pollo está refrigerado").condiciones

    def test_descongelado_rompe_la_cadena_y_no_cuenta_como_refrigerado(self):
        cond = extraer("el pollo se descongeló").condiciones
        assert "cadena_rota" in cond
        assert "refrigerado" not in cond and "congelado" not in cond

    def test_congelado(self):
        assert extraer("viene congelado").condiciones == ["congelado"]

    def test_mal_estado(self):
        assert "mal_estado" in extraer("la fruta ya tiene moho").condiciones

    def test_empacado(self):
        assert "empacado" in extraer("todo sellado y sin abrir").condiciones


class TestIntencion:
    @pytest.mark.parametrize("texto", ["sí", "Si", "Sí, correcto", "confirmo", "dale", "ok", "Sí, siempre en refri"])
    def test_confirmar(self, texto):
        assert extraer(texto).intencion == "confirmar"

    @pytest.mark.parametrize("texto", ["no", "No.", "nel", "incorrecto"])
    def test_negar(self, texto):
        assert extraer(texto).intencion == "negar"

    def test_no_con_correccion_es_una_nueva_donacion(self):
        ext = extraer("no, son 30 kg")
        assert ext.intencion == "donar"
        assert tuplas(ext) == [(None, 30.0, "kg")]

    @pytest.mark.parametrize("texto", ["cancelar", "mejor no", "olvídalo", "ya no quiero donar"])
    def test_cancelar(self, texto):
        assert extraer(texto).intencion == "cancelar"

    def test_saludo_no_es_donacion(self):
        assert extraer("hola buenas tardes").intencion == "otro"

    def test_confirmacion_con_datos_es_una_donacion(self):
        assert extraer("sí, tengo 25 kg de pan").intencion == "donar"
