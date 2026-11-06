"""Factores para convertir kilos rescatados en métricas de impacto (CP-07).

⚠️  SUPUESTOS A VALIDAR. Estos números son editables y definen las cifras que muestra el tablero:

* ``KG_POR_RACION``: cuántos kilos de alimento equivalen a una ración (una comida servida).
* ``RACIONES_POR_PERSONA_DIA``: cuántas raciones come una persona al día. Se usa para expresar
  "personas beneficiadas" como *personas alimentadas el equivalente a un día completo*.
* ``FACTORES_CO2E``: kg de CO2e por kg de alimento. Son valores de referencia aproximados de la
  huella de producción de cada tipo de alimento (Poore y Nemecek, 2018, vía Our World in Data).
  **Fueron tomados de memoria, sin verificarse contra la fuente**: revisar antes de la entrega final.
  Interpretación: producir ese alimento ya emitió esos gases; rescatarlo evita producir/desechar
  otro equivalente. No incluye el metano evitado en relleno sanitario.
"""

from __future__ import annotations

KG_POR_RACION = 0.5
RACIONES_POR_PERSONA_DIA = 3.0

# clave del catálogo -> kg CO2e / kg de alimento
FACTORES_CO2E: dict[str, float] = {
    "pan": 1.6,  # trigo y centeno ~1.57
    "tortilla": 1.7,  # maíz ~1.70
    "fruta": 0.8,  # mezcla de plátano/manzana/cítricos/otras frutas
    "verdura": 0.7,  # mezcla de raíces, hojas y jitomate
    "abarrotes": 2.0,  # mezcla de arroz, leguminosas, trigo y empacados
    "bebidas": 0.6,  # estimación gruesa (jugos y refrescos)
    "lacteos": 6.0,  # mezcla de leche (~3) y queso (~24)
    "huevo": 4.7,
    "pollo": 9.9,
    "cerdo": 12.3,
    "res": 60.0,  # entre res de rancho (~99) y de lechería (~33)
    "carne": 20.0,  # carne sin especificar: promedio grueso
    "pescado": 13.6,
    "embutidos": 12.3,  # se asume base de cerdo
    "preparado": 3.0,  # platillo mixto: estimación gruesa
    "desconocido": 2.0,
}


def factor_co2e(clave: str) -> float:
    """kg de CO2e por kg para la clave del catálogo (2.0 si no se conoce)."""
    return FACTORES_CO2E.get(clave, FACTORES_CO2E["desconocido"])
