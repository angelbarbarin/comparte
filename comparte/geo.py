"""Utilidades geográficas.

En el MVP no se usa una API de mapas (ver ``docs/ALCANCE_MVP.md``): la distancia por calles se
aproxima con la distancia en línea recta (Haversine) multiplicada por un factor de circuito, y el
tiempo de viaje con una velocidad media urbana. La interfaz ``distancia_calles_km`` /
``minutos_de_viaje`` es el punto único que habría que sustituir por OSRM o Google Maps.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

RADIO_TIERRA_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en línea recta entre dos coordenadas, en kilómetros."""
    f1, f2 = radians(lat1), radians(lat2)
    df = f2 - f1
    dl = radians(lon2 - lon1)
    a = sin(df / 2) ** 2 + cos(f1) * cos(f2) * sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def distancia_calles_km(
    lat1: float, lon1: float, lat2: float, lon2: float, factor_circuito: float = 1.3
) -> float:
    """Distancia estimada por calles (línea recta x factor de circuito)."""
    return haversine_km(lat1, lon1, lat2, lon2) * factor_circuito


def minutos_de_viaje(km: float, velocidad_kmh: float = 25.0) -> float:
    """Minutos para recorrer ``km`` a la velocidad media dada."""
    if velocidad_kmh <= 0:
        raise ValueError("La velocidad debe ser positiva")
    return km / velocidad_kmh * 60.0
