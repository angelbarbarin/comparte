"""Fixtures compartidas por todas las pruebas.

* Cada prueba usa una base SQLite **en memoria** nueva: no hay estado compartido ni archivos.
* El reloj se congela en un martes por la tarde (17:30) para que los receptores estén abiertos
  y los resultados no dependan de la hora real en que se corra la prueba.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from comparte import reloj
from comparte.db import crear_fabrica, crear_motor, crear_tablas

HORA_PRUEBAS = datetime(2026, 11, 10, 17, 30)  # martes


@pytest.fixture(autouse=True)
def reloj_congelado():
    reloj.congelar(HORA_PRUEBAS)
    yield HORA_PRUEBAS
    reloj.restablecer()


@pytest.fixture
def ajustes_prueba(tmp_path):
    """Ajustes aislados: motor de reglas, sin clave de API y carpeta de datos temporal."""
    from comparte.config import Ajustes, obtener_ajustes

    base = obtener_ajustes()
    return Ajustes(**{**base.__dict__, "carpeta_datos": tmp_path, "modo_llm": "reglas", "api_key": None,
                      "hora_demo": None})


@pytest.fixture
def motor():
    motor = crear_motor("sqlite://")
    crear_tablas(motor)
    yield motor
    motor.dispose()


@pytest.fixture
def fabrica(motor):
    return crear_fabrica(motor)


@pytest.fixture
def db(fabrica):
    sesion = fabrica()
    yield sesion
    sesion.close()
