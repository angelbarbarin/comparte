"""Contrato común de los "motores de lenguaje" del Agente Captador.

El Captador necesita convertir un mensaje en lenguaje natural (y opcionalmente una foto) en datos
estructurados. Hay dos implementaciones intercambiables detrás de la misma interfaz:

* ``ExtractorReglas``  (``reglas.py``): determinista, gratis y sin internet. Es el modo por defecto.
* ``ExtractorClaude``  (``claude.py``): usa un LLM con visión; entiende mejor el lenguaje coloquial y
  puede leer la foto del excedente.

Ambos devuelven una ``Extraccion``. La política de la conversación (qué preguntar, cuándo confirmar,
reglas de inocuidad) vive en el Captador, **no** en el motor de lenguaje, así que cambiar de motor no
cambia el comportamiento del agente.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

INTENCIONES = ("donar", "confirmar", "negar", "cancelar", "otro")

# Etiquetas de condición que puede devolver un motor (ver conocimiento/inocuidad.py).
CONDICIONES = (
    "mal_estado", "cadena_rota", "refrigerado", "congelado", "empacado", "abierto", "caliente",
)

# Una imagen adjunta: (bytes, tipo MIME), p. ej. (b"...", "image/jpeg").
Imagen = tuple[bytes, str]


@dataclass
class ItemExtraido:
    """Un alimento mencionado. Cualquier campo puede faltar y el Captador preguntará."""

    nombre: str | None  # None cuando el usuario solo dijo una cantidad ("20 kg")
    cantidad: float | None = None
    unidad: str | None = None  # unidad canónica: kg, g, ton, l, pieza, docena, caja, ...


@dataclass
class Extraccion:
    intencion: str = "otro"
    items: list[ItemExtraido] = field(default_factory=list)
    caduca_en: datetime | None = None
    recoleccion_desde: datetime | None = None
    recoleccion_hasta: datetime | None = None
    condiciones: list[str] = field(default_factory=list)
    notas: str | None = None


class Extractor(Protocol):
    nombre: str

    def extraer(
        self, texto: str, borrador: dict, ahora: datetime, imagen: Imagen | None = None
    ) -> Extraccion:
        """Interpreta ``texto`` (y ``imagen``) dado el ``borrador`` actual de la donación."""
        ...
