"""Pruebas del catálogo de alimentos, conversión de unidades y reglas de inocuidad."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from comparte.conocimiento import catalogo, inocuidad
from comparte.conocimiento.factores_impacto import factor_co2e

AHORA = datetime(2026, 11, 10, 17, 30)


def _item(clave: str, nombre: str | None = None) -> dict:
    al = catalogo.CATALOGO[clave]
    return {"nombre": nombre or al.nombre, "clave": clave,
            "almacenamiento": al.almacenamiento, "riesgo": al.riesgo}


class TestCatalogo:
    def test_normalizar_quita_acentos_y_mayusculas(self):
        assert catalogo.normalizar("  Jitomate MADURO, Piña  ") == "jitomate maduro, pina"

    @pytest.mark.parametrize(
        "texto, clave",
        [
            ("pan dulce", "pan"), ("bolillos", "pan"), ("tortillas", "tortilla"),
            ("mangos maduros", "fruta"), ("jitomates", "verdura"), ("frijoles", "abarrotes"),
            ("leche", "lacteos"), ("queso", "lacteos"), ("pollo", "pollo"),
            ("arroz con pollo", "preparado"), ("cerveza", "no_aceptado"),
            ("papas fritas", "abarrotes"), ("papas", "verdura"),
        ],
    )
    def test_reconoce_alimentos_y_plurales(self, texto, clave):
        encontrados = catalogo.buscar_alimentos(catalogo.normalizar(texto))
        assert encontrados, texto
        assert encontrados[0].alimento.clave == clave

    def test_el_sinonimo_largo_gana_al_corto(self):
        # "arroz con pollo" no debe leerse como "arroz" + "pollo"
        encontrados = catalogo.buscar_alimentos("arroz con pollo")
        assert [c.alimento.clave for c in encontrados] == ["preparado"]

    def test_no_reconoce_dentro_de_otras_palabras(self):
        assert catalogo.buscar_alimentos("panorama") == []
        assert catalogo.buscar_alimentos("copa") == []

    def test_todas_las_categorias_del_catalogo_existen(self):
        for al in catalogo.CATALOGO.values():
            assert al.categoria in catalogo.CATEGORIAS, al.clave

    def test_todos_los_alimentos_tienen_factor_de_co2e(self):
        for clave in catalogo.CATALOGO:
            if clave != "no_aceptado":
                assert factor_co2e(clave) > 0, clave


class TestUnidades:
    @pytest.mark.parametrize(
        "texto, canonica",
        [("kilos", "kg"), ("kgs", "kg"), ("gramos", "g"), ("litros", "l"), ("cajas", "caja"),
         ("piezas", "pieza"), ("docenas", "docena"), ("racion", "porcion")],
    )
    def test_unidad_canonica(self, texto, canonica):
        assert catalogo.unidad_canonica(texto) == canonica

    def test_unidad_desconocida(self):
        assert catalogo.unidad_canonica("camionetas") is None

    def test_kilos_son_exactos(self):
        assert catalogo.a_kg(25, "kg", catalogo.CATALOGO["pan"]) == (25, False)
        assert catalogo.a_kg(500, "g", catalogo.CATALOGO["pan"]) == (0.5, False)
        assert catalogo.a_kg(2, "ton", catalogo.CATALOGO["pan"]) == (2000, False)

    def test_piezas_y_cajas_son_estimadas(self):
        kg, estimado = catalogo.a_kg(100, "pieza", catalogo.CATALOGO["pan"])
        assert kg == pytest.approx(7.0) and estimado
        kg, estimado = catalogo.a_kg(2, "docena", catalogo.CATALOGO["huevo"])
        assert kg == pytest.approx(1.44) and estimado
        kg, estimado = catalogo.a_kg(3, "caja", catalogo.CATALOGO["fruta"])
        assert kg == pytest.approx(30.0) and estimado


class TestInocuidad:
    def test_pan_con_margen_amplio_es_bajo_riesgo(self):
        ev = inocuidad.evaluar([_item("pan")], [], AHORA + timedelta(hours=8), AHORA)
        assert (ev.nivel, ev.bloqueada, ev.requiere_revision, ev.requiere_frio) == (
            "bajo", False, False, False)

    def test_lacteos_requieren_revision_humana_y_frio(self):
        ev = inocuidad.evaluar([_item("lacteos")], [], AHORA + timedelta(hours=30), AHORA)
        assert ev.nivel == "alto"
        assert ev.requiere_revision and ev.requiere_frio
        assert ev.confirmar_frio  # hay que preguntar si se mantuvo refrigerado
        assert not ev.bloqueada

    def test_con_refrigeracion_confirmada_ya_no_se_pregunta(self):
        ev = inocuidad.evaluar([_item("pollo")], ["refrigerado"], AHORA + timedelta(hours=20), AHORA)
        assert ev.requiere_revision and not ev.confirmar_frio

    def test_cadena_de_frio_rota_bloquea(self):
        ev = inocuidad.evaluar([_item("pollo")], ["cadena_rota"], AHORA + timedelta(hours=20), AHORA)
        assert ev.bloqueada
        assert any("cadena de frío" in m for m in ev.motivos)

    def test_producto_caducado_bloquea(self):
        ev = inocuidad.evaluar([_item("pan")], [], AHORA - timedelta(minutes=1), AHORA)
        assert ev.bloqueada
        assert any("caducado" in m for m in ev.motivos)

    def test_mal_estado_bloquea(self):
        ev = inocuidad.evaluar([_item("fruta")], ["mal_estado"], AHORA + timedelta(hours=10), AHORA)
        assert ev.bloqueada

    def test_alcohol_no_se_acepta(self):
        ev = inocuidad.evaluar([_item("no_aceptado", "cerveza")], [], AHORA + timedelta(days=5), AHORA)
        assert ev.bloqueada
        assert any("cerveza" in m for m in ev.motivos)

    def test_comida_preparada_limita_el_transporte(self):
        ev = inocuidad.evaluar([_item("preparado")], [], AHORA + timedelta(hours=5), AHORA)
        assert ev.horas_max_transporte == inocuidad.HORAS_MAX_TRANSPORTE_PREPARADO
        assert ev.requiere_revision

    def test_alimento_desconocido_pasa_a_revision(self):
        item = {"nombre": "sushi", "clave": "desconocido", "almacenamiento": "ambiente", "riesgo": "medio"}
        ev = inocuidad.evaluar([item], [], AHORA + timedelta(hours=10), AHORA)
        assert ev.requiere_revision and not ev.bloqueada

    def test_caducidad_cercana_sube_el_nivel_y_avisa(self):
        ev = inocuidad.evaluar([_item("pan")], [], AHORA + timedelta(hours=2), AHORA)
        assert ev.nivel == "medio"
        assert ev.advertencias

    def test_empaque_abierto_en_alimento_de_bajo_riesgo_solo_advierte(self):
        ev = inocuidad.evaluar([_item("abarrotes")], ["abierto"], AHORA + timedelta(days=30), AHORA)
        assert not ev.bloqueada and ev.advertencias

    def test_empaque_abierto_en_alimento_de_riesgo_bloquea(self):
        ev = inocuidad.evaluar([_item("lacteos")], ["abierto", "refrigerado"],
                               AHORA + timedelta(days=2), AHORA)
        assert ev.bloqueada
