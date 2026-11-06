"""Agente Logístico (CP-05 Coordinación de recolección, y la parte de voluntarios de CP-06).

Cuando un receptor acepta una donación, busca al voluntario que la lleve, calcula la ruta
(voluntario -> donante -> receptor), propone la recolección con tiempo límite y le da seguimiento hasta
la entrega. Como el Coordinador, es **explicable**: guarda la ruta, los tiempos estimados y el motivo
de cada voluntario descartado.

Reglas para que un voluntario sea viable (cada descarte conserva su motivo):
disponible; sin otra recolección en curso; vehículo con capacidad suficiente; con hielera si la donación
requiere cadena de frío; dentro de su horario; llega dentro de la ventana de recolección del donante;
alcanza a entregar antes de que caduque y antes de que cierre el receptor; y respeta el tiempo máximo de
traslado de la comida preparada. De los viables se elige al de **menor tiempo total de ruta**.

Limitaciones del MVP: los voluntarios son simulados (ubicación base fija); la ruta es una estimación en
línea recta x factor de circuito (ver ``geo.py``); una recolección = un voluntario.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reloj
from ..config import Ajustes, obtener_ajustes
from ..geo import distancia_calles_km, minutos_de_viaje
from ..modelos import (
    Agente,
    Donacion,
    EstadoDonacion,
    EstadoRecoleccion,
    Recoleccion,
    Voluntario,
)
from .base import a_iso, fmt_momento, notificar_donante, registrar_evento

RETRASO_SALIDA_MIN = 5  # tiempo para que el voluntario acepte y salga
TIEMPO_CARGA_MIN = 5  # tiempo en el punto del donante y en el del receptor
MARGEN_ENTREGA_MIN = 15  # la entrega debe terminar 15 min antes de caducar
_ACTIVOS = (EstadoRecoleccion.PROPUESTA, EstadoRecoleccion.ACEPTADA, EstadoRecoleccion.RECOGIDA)


@dataclass
class CandidatoVoluntario:
    voluntario: Voluntario
    motivos_exclusion: list[str] = field(default_factory=list)
    duracion_total_min: float = 0.0
    distancia_total_km: float = 0.0
    recoger: datetime | None = None
    entrega: datetime | None = None
    ruta: dict = field(default_factory=dict)

    @property
    def viable(self) -> bool:
        return not self.motivos_exclusion

    def a_dict(self) -> dict:
        return {
            "voluntario_id": self.voluntario.id, "nombre": self.voluntario.nombre,
            "viable": self.viable, "motivos_exclusion": self.motivos_exclusion,
            "duracion_total_min": round(self.duracion_total_min), "distancia_total_km": round(self.distancia_total_km, 1),
            "recoger": a_iso(self.recoger), "entrega": a_iso(self.entrega),
        }


class AgenteLogistico:
    nombre = Agente.LOGISTICO

    def __init__(self, db: Session, ajustes: Ajustes | None = None):
        self.db = db
        self.ajustes = ajustes or obtener_ajustes()

    # ------------------------------------------------------------------ ruta
    def _ruta(self, v: Voluntario, donacion: Donacion) -> dict:
        d, r = donacion.donante, donacion.receptor
        f, vel = self.ajustes.factor_circuito, self.ajustes.velocidad_kmh
        km1 = distancia_calles_km(v.lat, v.lon, d.lat, d.lon, f)
        km2 = distancia_calles_km(d.lat, d.lon, r.lat, r.lon, f)
        return {
            "puntos": [
                {"rol": "voluntario", "nombre": v.nombre, "lat": v.lat, "lon": v.lon},
                {"rol": "donante", "nombre": d.nombre, "lat": d.lat, "lon": d.lon},
                {"rol": "receptor", "nombre": r.nombre, "lat": r.lat, "lon": r.lon},
            ],
            "tramos": [
                {"de": "voluntario", "a": "donante", "km": round(km1, 1), "min": round(minutos_de_viaje(km1, vel))},
                {"de": "donante", "a": "receptor", "km": round(km2, 1), "min": round(minutos_de_viaje(km2, vel))},
            ],
            "distancia_km": round(km1 + km2, 1),
            "duracion_min": round(minutos_de_viaje(km1, vel) + minutos_de_viaje(km2, vel)),
            "_min1": minutos_de_viaje(km1, vel), "_min2": minutos_de_viaje(km2, vel),
        }

    # ------------------------------------------------------------------ evaluación
    def evaluar_voluntarios(self, donacion: Donacion, excluir: set[int] | None = None) -> list[CandidatoVoluntario]:
        ahora = reloj.ahora()
        excluir = excluir or set()
        ocupados = set(self.db.scalars(
            select(Recoleccion.voluntario_id).where(
                Recoleccion.estado.in_(_ACTIVOS), Recoleccion.donacion_id != donacion.id
            )
        ))
        receptor = donacion.receptor
        limite_h = (donacion.inocuidad or {}).get("horas_max_transporte")
        candidatos: list[CandidatoVoluntario] = []

        for v in self.db.scalars(select(Voluntario).order_by(Voluntario.id)):
            ruta = self._ruta(v, donacion)
            llegada_donante = ahora + timedelta(minutes=RETRASO_SALIDA_MIN + ruta["_min1"])
            recoger = max(llegada_donante, donacion.recoleccion_desde)
            entrega = recoger + timedelta(minutes=TIEMPO_CARGA_MIN + ruta["_min2"])
            publica = {k: x for k, x in ruta.items() if not k.startswith("_")}
            c = CandidatoVoluntario(
                voluntario=v, duracion_total_min=ruta["_min1"] + ruta["_min2"],
                distancia_total_km=ruta["distancia_km"], recoger=recoger, entrega=entrega, ruta=publica,
            )

            if v.id in excluir:
                c.motivos_exclusion.append("ya rechazó u omitió esta recolección")
            if not v.disponible:
                c.motivos_exclusion.append("no está disponible")
            if v.id in ocupados:
                c.motivos_exclusion.append("tiene otra recolección en curso")
            if v.capacidad_kg < donacion.total_kg:
                c.motivos_exclusion.append(
                    f"su vehículo ({v.vehiculo}) carga {v.capacidad_kg:.0f} kg y la donación pesa {donacion.total_kg:.0f} kg"
                )
            if donacion.requiere_frio and not v.tiene_hielera:
                c.motivos_exclusion.append("sin hielera para la cadena de frío")
            if not (reloj.a_hora(v.disponible_desde, recoger) <= recoger <= reloj.a_hora(v.disponible_hasta, recoger)):
                c.motivos_exclusion.append(
                    f"fuera de su horario ({v.disponible_desde}-{v.disponible_hasta})"
                )
            if recoger > donacion.recoleccion_hasta:
                c.motivos_exclusion.append(
                    f"no llega dentro de la ventana de recolección (hasta {donacion.recoleccion_hasta:%H:%M})"
                )
            if entrega + timedelta(minutes=MARGEN_ENTREGA_MIN) > donacion.caduca_en:
                c.motivos_exclusion.append("no alcanza a entregar antes de que caduque")
            if entrega > reloj.a_hora(receptor.horario_cierre, entrega):
                c.motivos_exclusion.append(f"el receptor ya habría cerrado ({receptor.horario_cierre})")
            if limite_h and ruta["_min2"] / 60.0 > limite_h:
                c.motivos_exclusion.append(f"el traslado excede el máximo de {limite_h:g} h")
            candidatos.append(c)

        candidatos.sort(key=lambda c: (not c.viable, c.duracion_total_min, c.voluntario.id))
        return candidatos

    # ------------------------------------------------------------------ ciclo de la recolección
    def proponer(self, donacion: Donacion, reiniciar: bool = False) -> Recoleccion | None:
        """Propone la recolección al mejor voluntario que no la haya rechazado/omitido.

        Con ``reiniciar=True`` (reintento del administrador) se ignoran los rechazos anteriores.
        """
        ahora = reloj.ahora()
        previas = list(self.db.scalars(
            select(Recoleccion).where(
                Recoleccion.donacion_id == donacion.id,
                Recoleccion.estado.in_((EstadoRecoleccion.RECHAZADA, EstadoRecoleccion.EXPIRADA)),
            )
        ))
        candidatos = self.evaluar_voluntarios(
            donacion, set() if reiniciar else {p.voluntario_id for p in previas}
        )
        viables = [c for c in candidatos if c.viable]
        if not viables:
            donacion.estado = EstadoDonacion.SIN_VOLUNTARIO
            registrar_evento(
                self.db, self.nombre, "sin_voluntario",
                "Ningún voluntario puede hacer esta recolección; queda en espera de atención del administrador.",
                donacion_id=donacion.id,
                detalle={"descartados": {c.voluntario.nombre: c.motivos_exclusion for c in candidatos}},
            )
            notificar_donante(self.db, donacion, self.nombre,
                              "Tu donación ya tiene receptor, pero aún no encuentro un voluntario que pueda "
                              "recogerla. Un administrador intervendrá.")
            return None

        mejor = viables[0]
        recoleccion = Recoleccion(
            donacion_id=donacion.id, voluntario_id=mejor.voluntario.id, estado=EstadoRecoleccion.PROPUESTA,
            ruta=mejor.ruta, recoger_estimado=mejor.recoger, entrega_estimada=mejor.entrega,
            justificacion=(
                f"Mejor de {len(viables)} voluntario{'s' if len(viables) != 1 else ''} viable{'s' if len(viables) != 1 else ''}: "
                f"ruta de {mejor.distancia_total_km:.1f} km (~{mejor.duracion_total_min:.0f} min), "
                f"recoge {fmt_momento(mejor.recoger, ahora)} y entrega {fmt_momento(mejor.entrega, ahora)}."
            ),
            creada_en=ahora, vence_en=ahora + timedelta(minutes=self.ajustes.vigencia_recoleccion_min),
        )
        self.db.add(recoleccion)
        if donacion.estado == EstadoDonacion.SIN_VOLUNTARIO:  # reintento exitoso: ya hay propuesta en curso
            donacion.estado = EstadoDonacion.ASIGNADA
        self.db.flush()
        registrar_evento(
            self.db, self.nombre, "recoleccion_propuesta" if not previas else "recoleccion_reasignada",
            f"Propuse la recolección a {mejor.voluntario.nombre} ({mejor.voluntario.vehiculo}). {recoleccion.justificacion}",
            donacion_id=donacion.id,
            detalle={"recoleccion_id": recoleccion.id, "candidatos": [c.a_dict() for c in candidatos]},
        )
        return recoleccion

    def responder(self, recoleccion: Recoleccion, aceptar: bool, motivo: str | None = None) -> Recoleccion:
        ahora = reloj.ahora()
        if recoleccion.estado != EstadoRecoleccion.PROPUESTA:
            raise ValueError(f"La recolección {recoleccion.id} ya no está propuesta ({recoleccion.estado})")
        donacion, v = recoleccion.donacion, recoleccion.voluntario
        recoleccion.respondida_en = ahora
        if aceptar:
            recoleccion.estado = EstadoRecoleccion.ACEPTADA
            donacion.estado = EstadoDonacion.EN_RECOLECCION
            registrar_evento(self.db, self.nombre, "recoleccion_aceptada",
                             f"{v.nombre} aceptó la recolección.", donacion_id=donacion.id)
            notificar_donante(
                self.db, donacion, self.nombre,
                f"{v.nombre} ({v.vehiculo}) pasará por tu donación hacia las "
                f"{recoleccion.recoger_estimado:%H:%M} y la llevará a {donacion.receptor.nombre}.",
            )
        else:
            recoleccion.estado = EstadoRecoleccion.RECHAZADA
            recoleccion.motivo = motivo or "Sin motivo indicado"
            registrar_evento(self.db, self.nombre, "recoleccion_rechazada",
                             f"{v.nombre} rechazó la recolección: {recoleccion.motivo}.", donacion_id=donacion.id)
        return recoleccion

    def avanzar(self, recoleccion: Recoleccion, nuevo_estado: str) -> Recoleccion:
        """Registra que el voluntario recogió (``recogida``) o entregó (``entregada``) la donación."""
        ahora = reloj.ahora()
        donacion, v = recoleccion.donacion, recoleccion.voluntario
        if nuevo_estado == EstadoRecoleccion.RECOGIDA and recoleccion.estado == EstadoRecoleccion.ACEPTADA:
            recoleccion.estado, recoleccion.recogida_en = EstadoRecoleccion.RECOGIDA, ahora
            donacion.estado = EstadoDonacion.EN_CAMINO
            registrar_evento(self.db, self.nombre, "donacion_recogida",
                             f"{v.nombre} recogió la donación en {donacion.donante.nombre}.", donacion_id=donacion.id)
            notificar_donante(self.db, donacion, self.nombre,
                              f"{v.nombre} ya recogió tu donación y va rumbo a {donacion.receptor.nombre}. ¡Gracias!")
        elif nuevo_estado == EstadoRecoleccion.ENTREGADA and recoleccion.estado == EstadoRecoleccion.RECOGIDA:
            recoleccion.estado, recoleccion.entregada_en = EstadoRecoleccion.ENTREGADA, ahora
            donacion.estado, donacion.entregada_en = EstadoDonacion.ENTREGADA, ahora
            registrar_evento(self.db, self.nombre, "donacion_entregada",
                             f"{v.nombre} entregó la donación en {donacion.receptor.nombre}; falta que el receptor confirme.",
                             donacion_id=donacion.id)
        else:
            raise ValueError(f"No se puede pasar de '{recoleccion.estado}' a '{nuevo_estado}'")
        return recoleccion

    def expirar_vencidas(self) -> list[Recoleccion]:
        ahora = reloj.ahora()
        vencidas = list(self.db.scalars(
            select(Recoleccion).where(Recoleccion.estado == EstadoRecoleccion.PROPUESTA, Recoleccion.vence_en <= ahora)
        ))
        for r in vencidas:
            r.estado, r.respondida_en, r.motivo = EstadoRecoleccion.EXPIRADA, ahora, "No respondió a tiempo"
            registrar_evento(
                self.db, self.nombre, "recoleccion_expirada",
                f"{r.voluntario.nombre} no respondió en {self.ajustes.vigencia_recoleccion_min} min; busco otro voluntario.",
                donacion_id=r.donacion_id,
            )
        return vencidas
