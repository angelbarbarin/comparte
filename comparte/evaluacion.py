"""Medición de la precisión de un motor de lenguaje del Captador (rango de calidad de la sección 7).

El documento de visión pide "≥ 90 % de donaciones correctamente estructuradas (tipo y cantidad)".
Aquí un mensaje cuenta como correcto solo si **todos** sus alimentos se reconocen con el tipo
(clave del catálogo), la cantidad y la unidad esperados, y no sobra ni falta ninguno. Es una vara
exigente a propósito.

Los mensajes de ``tests/data/mensajes_captador.json`` los escribió el equipo: sirven como línea base y
para detectar regresiones, **no** como validación con datos reales.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .agentes.captador import resolver_alimento
from .llm.base import Extractor

RUTA_CASOS = Path(__file__).resolve().parent.parent / "tests" / "data" / "mensajes_captador.json"


@dataclass
class Fallo:
    texto: str
    esperado: list[tuple]
    obtenido: list[tuple]
    lote: str = "A"


@dataclass
class Resultado:
    total: int = 0
    correctos: int = 0
    fallos: list[Fallo] = field(default_factory=list)
    por_lote: dict[str, list[int]] = field(default_factory=dict)  # lote -> [correctos, total]

    @property
    def exactitud(self) -> float:
        return self.correctos / self.total if self.total else 0.0

    def exactitud_lote(self, lote: str) -> float:
        correctos, total = self.por_lote.get(lote, [0, 0])
        return correctos / total if total else 0.0


def cargar_casos(ruta: Path = RUTA_CASOS) -> list[dict]:
    return json.loads(ruta.read_text(encoding="utf-8"))["casos"]


def _normalizar(items: list[tuple]) -> list[tuple]:
    filas = [(c, float(q) if q is not None else None, u) for c, q, u in items]
    return sorted(filas, key=lambda t: (t[0], -1.0 if t[1] is None else t[1], t[2] or ""))


def evaluar_extractor(extractor: Extractor, casos: list[dict] | None = None, ahora: datetime | None = None) -> Resultado:
    casos = casos if casos is not None else cargar_casos()
    ahora = ahora or datetime(2026, 11, 10, 17, 30)
    resultado = Resultado()
    for caso in casos:
        extraccion = extractor.extraer(caso["texto"], {}, ahora)
        obtenido = [(resolver_alimento(i.nombre or "").clave, i.cantidad, i.unidad) for i in extraccion.items]
        esperado = [tuple(e) for e in caso["esperado"]]
        lote = caso.get("lote", "A")
        acumulado = resultado.por_lote.setdefault(lote, [0, 0])
        resultado.total += 1
        acumulado[1] += 1
        if _normalizar(obtenido) == _normalizar(esperado):
            resultado.correctos += 1
            acumulado[0] += 1
        else:
            resultado.fallos.append(Fallo(caso["texto"], esperado, obtenido, lote))
    return resultado
