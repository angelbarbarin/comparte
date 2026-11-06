"""Guarda contra regresiones de la precisión del motor de reglas (no es una validación con datos reales).

Estos umbrales son pisos de regresión, no la meta. La cifra a reportar es la que imprime
``scripts/evaluar_captador.py`` (lote B = escrito después de corregir el motor). Los mensajes los escribió
el equipo; ver ``comparte/evaluacion.py``.
"""

from __future__ import annotations

from comparte.evaluacion import cargar_casos, evaluar_extractor
from comparte.llm.reglas import ExtractorReglas


def test_el_conjunto_de_casos_esta_bien_formado():
    casos = cargar_casos()
    assert len(casos) >= 50
    assert {c.get("lote", "A") for c in casos} == {"A", "B"}
    assert all(c["texto"].strip() and c["esperado"] for c in casos)


def test_el_motor_de_reglas_no_baja_de_su_piso_de_precision():
    r = evaluar_extractor(ExtractorReglas())
    assert r.exactitud_lote("A") >= 0.95, [f.texto for f in r.fallos if f.lote == "A"]
    assert r.exactitud_lote("B") >= 0.85, [f.texto for f in r.fallos if f.lote == "B"]
    assert r.exactitud >= 0.90


def test_los_fallos_conocidos_son_alimentos_fuera_del_catalogo():
    """Documenta la limitación real: sin unidad y fuera del catálogo el motor de reglas no ve el alimento."""
    fallos = {f.texto for f in evaluar_extractor(ExtractorReglas()).fallos}
    assert fallos <= {"me sobraron 30 empanadas", "3 bolsas de tortillas y 2 de totopos"}
