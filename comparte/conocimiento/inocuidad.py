"""Reglas de inocuidad (CP-02).

Dado el contenido de una donación, decide:

* si **se bloquea** (no puede donarse: caducado, mal estado, cadena de frío rota, no aceptado),
* si **requiere revisión humana** (alimentos de riesgo alto o no reconocidos; la supervisión humana
  de las decisiones sensibles es un requisito del documento de visión, sección 4.1),
* si **requiere cadena de frío** (y por tanto un receptor con refrigeración y un voluntario con hielera).

⚠️  Son reglas heurísticas del equipo inspiradas en buenas prácticas de manejo higiénico (la
sección 9.1 del documento de visión menciona la NOM-251-SSA1-2009 como base). **No son una
certificación sanitaria**; la responsabilidad de inocuidad es de donantes y receptores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

NIVELES = ("bajo", "medio", "alto")

# Etiquetas de condición que entiende el sistema (las produce el extractor de lenguaje).
COND_MAL_ESTADO = "mal_estado"
COND_CADENA_ROTA = "cadena_rota"
COND_ABIERTO = "abierto"
COND_FRIO_OK = "cadena_frio_ok"
COND_REFRIGERADO = "refrigerado"
COND_CONGELADO = "congelado"

MARGEN_CADUCIDAD_CRITICO_H = 3.0  # menos de esto para caducar => nivel al menos "medio"
HORAS_MAX_TRANSPORTE_PREPARADO = 2.0


@dataclass
class Evaluacion:
    nivel: str = "bajo"
    bloqueada: bool = False
    requiere_revision: bool = False
    requiere_frio: bool = False
    confirmar_frio: bool = False  # hay que preguntarle al donante si se mantuvo la cadena de frío
    motivos: list[str] = field(default_factory=list)  # por qué se bloquea / revisa
    advertencias: list[str] = field(default_factory=list)
    horas_max_transporte: float | None = None

    def a_dict(self) -> dict:
        return asdict(self)


def frio_confirmado(condiciones: list[str]) -> bool:
    return any(c in condiciones for c in (COND_FRIO_OK, COND_REFRIGERADO, COND_CONGELADO))


def evaluar(
    items: list[dict], condiciones: list[str], caduca_en: datetime, ahora: datetime
) -> Evaluacion:
    """Evalúa una donación. ``items`` trae por elemento: ``nombre, clave, almacenamiento, riesgo``."""
    ev = Evaluacion()
    riesgos = ["bajo"]

    for it in items:
        nombre = it.get("nombre", "alimento")
        riesgo = it.get("riesgo", "medio")
        clave = it.get("clave", "desconocido")
        almacenamiento = it.get("almacenamiento", "ambiente")

        if clave == "no_aceptado":
            ev.bloqueada = True
            ev.motivos.append(
                f"'{nombre}' no se acepta: ComParte no gestiona alcohol, medicamentos ni tabaco."
            )
            continue
        if clave == "desconocido":
            ev.requiere_revision = True
            ev.motivos.append(f"'{nombre}' no está en el catálogo: una persona debe revisarlo.")
        if riesgo == "alto":
            ev.requiere_revision = True
            ev.motivos.append(f"'{nombre}' es un alimento de riesgo alto: requiere validación humana.")
        if almacenamiento == "refrigerado":
            ev.requiere_frio = True
        if almacenamiento == "preparado":
            ev.horas_max_transporte = HORAS_MAX_TRANSPORTE_PREPARADO
            ev.advertencias.append(
                f"'{nombre}' es comida preparada: debe entregarse en menos de "
                f"{HORAS_MAX_TRANSPORTE_PREPARADO:.0f} h y consumirse el mismo día."
            )
        riesgos.append(riesgo)

    if COND_MAL_ESTADO in condiciones:
        ev.bloqueada = True
        ev.motivos.append("El donante reporta alimento en mal estado (moho, descompuesto o similar).")

    if COND_CADENA_ROTA in condiciones and ev.requiere_frio:
        ev.bloqueada = True
        ev.motivos.append("Se rompió la cadena de frío: el alimento refrigerado ya no es seguro.")

    if COND_ABIERTO in condiciones:
        if any(r != "bajo" for r in riesgos):
            ev.bloqueada = True
            ev.motivos.append("Empaque abierto en un alimento de riesgo: no puede donarse.")
        else:
            ev.advertencias.append("El empaque está abierto: el receptor debe revisarlo al recibir.")

    margen_h = (caduca_en - ahora).total_seconds() / 3600.0
    if margen_h <= 0:
        ev.bloqueada = True
        ev.motivos.append("El alimento ya está caducado.")
    elif margen_h < MARGEN_CADUCIDAD_CRITICO_H:
        ev.advertencias.append(f"Caduca en menos de {MARGEN_CADUCIDAD_CRITICO_H:.0f} h: es urgente.")
        riesgos.append("medio")

    if ev.requiere_frio and not frio_confirmado(condiciones) and not ev.bloqueada:
        ev.confirmar_frio = True

    ev.nivel = max(riesgos, key=NIVELES.index)
    if ev.requiere_revision and ev.nivel == "bajo":
        ev.nivel = "medio"
    return ev
