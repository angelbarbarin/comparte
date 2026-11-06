"""Agente Coordinador (CP-03 Perfil de receptores y CP-04 Asignación inteligente).

Elige al receptor óptimo para cada donación, le hace una **oferta con tiempo límite** y, si la
rechaza o no responde, reasigna al siguiente. Cada decisión es **explicable**: se guarda el desglose
del puntaje de todos los receptores evaluados y el motivo de exclusión de los descartados.

Cómo decide
-----------
1. *Filtros duros* (el receptor se descarta y se anota por qué): no verificado; sin cadena de frío o
   sin espacio refrigerado; sin capacidad de recepción hoy; cerrado cuando llegaría; no llega antes de
   que caduque (con margen); excedería el tiempo máximo de transporte; y, si hay receptores que sí lo
   necesitan, los que no necesitan nada de lo donado ("recibir solo lo que se puede usar").
2. *Puntaje 0-100* = suma ponderada de cinco componentes entre 0 y 1 (ver ``PESOS``):
   necesidad, cercanía, margen de caducidad, capacidad y equidad.
   La **equidad** (receptores que han recibido menos en los últimos 7 días puntúan más) es la medida
   concreta contra la restricción ética del documento de visión: *no discriminar entre receptores*.

Limitaciones del MVP: una donación va a un solo receptor (no se divide); la llegada se estima con
distancia en línea recta x factor de circuito y una velocidad media (ver ``geo.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import reloj
from ..config import Ajustes, obtener_ajustes
from ..conocimiento.catalogo import CATEGORIAS
from ..geo import distancia_calles_km, minutos_de_viaje
from ..modelos import (
    Agente,
    Donacion,
    EstadoDonacion,
    EstadoOferta,
    Oferta,
    Receptor,
)
from .base import a_iso, fmt_kg, fmt_momento, notificar_donante, registrar_evento

PESOS = {"necesidad": 0.30, "cercania": 0.20, "caducidad": 0.20, "capacidad": 0.20, "equidad": 0.10}
DISTANCIA_MAX_KM = 30.0  # a esta distancia por calles la cercanía vale 0
PREPARACION_MIN = 20  # minutos que se asumen entre la oferta y la recolección
MARGEN_MINIMO_MIN = 30  # la entrega debe terminar al menos 30 min antes de caducar
FRACCION_VIDA_IDEAL = 0.5  # llegar con >= 50 % de la vida restante da el puntaje máximo de caducidad
HOLGURA_CAPACIDAD = 2.0  # tener espacio para 2x lo donado da el puntaje máximo de capacidad

_ESTADOS_COMPROMETIDOS = (
    EstadoDonacion.ASIGNADA, EstadoDonacion.EN_RECOLECCION, EstadoDonacion.EN_CAMINO,
    EstadoDonacion.ENTREGADA, EstadoDonacion.COMPLETADA,
)


@dataclass
class Candidato:
    receptor: Receptor
    distancia_km: float
    llegada: datetime
    componentes: dict[str, float] = field(default_factory=dict)  # cada uno entre 0 y 1
    puntaje: float = 0.0
    motivos_exclusion: list[str] = field(default_factory=list)
    kg_disponibles: float = 0.0  # capacidad que le queda hoy (la de frío si la donación lo requiere)
    categorias_cubiertas: list[str] = field(default_factory=list)

    @property
    def viable(self) -> bool:
        return not self.motivos_exclusion

    def a_dict(self) -> dict:
        return {
            "receptor_id": self.receptor.id, "nombre": self.receptor.nombre,
            "viable": self.viable, "puntaje": round(self.puntaje, 1),
            "componentes": {k: round(v, 2) for k, v in self.componentes.items()},
            "distancia_km": round(self.distancia_km, 1), "llegada": a_iso(self.llegada),
            "motivos_exclusion": self.motivos_exclusion, "kg_disponibles": round(self.kg_disponibles, 1),
        }


class AgenteCoordinador:
    nombre = Agente.COORDINADOR

    def __init__(self, db: Session, ajustes: Ajustes | None = None):
        self.db = db
        self.ajustes = ajustes or obtener_ajustes()

    # ------------------------------------------------------------------ consultas de capacidad
    def _comprometido_hoy(self, receptor: Receptor, ahora: datetime, solo_frio: bool) -> float:
        """kg ya asignados hoy al receptor, más los de ofertas pendientes (reservados)."""
        inicio = datetime.combine(ahora.date(), time.min)
        asignadas = self.db.scalars(
            select(Donacion).where(
                Donacion.receptor_id == receptor.id,
                Donacion.estado.in_(_ESTADOS_COMPROMETIDOS),
                Donacion.asignada_en >= inicio,
            )
        )
        pendientes = self.db.scalars(
            select(Donacion).join(Oferta).where(
                Oferta.receptor_id == receptor.id, Oferta.estado == EstadoOferta.PENDIENTE
            )
        )
        donaciones = [*asignadas, *pendientes]
        return sum(d.total_kg for d in donaciones if d.requiere_frio or not solo_frio)

    def _recibido_7_dias(self, receptor: Receptor, ahora: datetime) -> float:
        desde = ahora - timedelta(days=7)
        return sum(
            d.total_kg
            for d in self.db.scalars(
                select(Donacion).where(
                    Donacion.receptor_id == receptor.id,
                    Donacion.estado.in_(_ESTADOS_COMPROMETIDOS),
                    Donacion.asignada_en >= desde,
                )
            )
        )

    # ------------------------------------------------------------------ evaluación
    def evaluar_receptores(self, donacion: Donacion, excluir: set[int] | None = None) -> list[Candidato]:
        """Evalúa a todos los receptores. Devuelve primero los viables (mejor puntaje primero)."""
        ahora = reloj.ahora()
        excluir = excluir or set()
        donante = donacion.donante
        recogida = max(ahora + timedelta(minutes=PREPARACION_MIN), donacion.recoleccion_desde)
        limite_transporte_h = (donacion.inocuidad or {}).get("horas_max_transporte")
        vida_restante_h = max((donacion.caduca_en - ahora).total_seconds() / 3600.0, 0.01)

        candidatos: list[Candidato] = []
        for r in self.db.scalars(select(Receptor).order_by(Receptor.id)):
            km = distancia_calles_km(donante.lat, donante.lon, r.lat, r.lon, self.ajustes.factor_circuito)
            viaje_min = minutos_de_viaje(km, self.ajustes.velocidad_kmh)
            llegada = recogida + timedelta(minutes=viaje_min)
            apertura = reloj.a_hora(r.horario_apertura, llegada)
            cierre = reloj.a_hora(r.horario_cierre, llegada)
            llegada_efectiva = max(llegada, apertura)
            c = Candidato(receptor=r, distancia_km=km, llegada=llegada_efectiva)

            disponible_frio = r.capacidad_frio_kg - self._comprometido_hoy(r, ahora, solo_frio=True)
            disponible_seco = r.capacidad_diaria_kg - self._comprometido_hoy(r, ahora, solo_frio=False)
            c.kg_disponibles = disponible_frio if donacion.requiere_frio else disponible_seco

            # ---- filtros duros -------------------------------------------------------------
            if r.id in excluir:
                c.motivos_exclusion.append("ya rechazó u omitió esta oferta")
            if not r.verificado:
                c.motivos_exclusion.append("organización sin verificar")
            if donacion.requiere_frio and r.capacidad_frio_kg <= 0:
                c.motivos_exclusion.append("sin refrigeración (la donación requiere cadena de frío)")
            elif c.kg_disponibles < donacion.total_kg:
                c.motivos_exclusion.append(
                    f"capacidad insuficiente (le quedan {max(c.kg_disponibles, 0):.0f} kg hoy)"
                )
            if llegada_efectiva > cierre:
                c.motivos_exclusion.append(f"cerrado al llegar (cierra a las {r.horario_cierre})")
            elif llegada_efectiva + timedelta(minutes=MARGEN_MINIMO_MIN) > donacion.caduca_en:
                c.motivos_exclusion.append("no llegaría antes de que caduque")
            if limite_transporte_h and viaje_min / 60.0 > limite_transporte_h:
                c.motivos_exclusion.append(f"el traslado excede el máximo de {limite_transporte_h:g} h")

            # ---- componentes del puntaje ---------------------------------------------------
            c.componentes = self._componentes(donacion, r, c, vida_restante_h, ahora)
            c.puntaje = 100.0 * sum(PESOS[k] * v for k, v in c.componentes.items())
            candidatos.append(c)

        # Si alguien sí necesita lo donado, no se ofrece a quien no necesita nada de eso.
        viables = [c for c in candidatos if c.viable]
        if any(c.componentes["necesidad"] > 0 for c in viables):
            for c in viables:
                if c.componentes["necesidad"] == 0:
                    c.motivos_exclusion.append("no necesita ninguno de los alimentos donados")

        candidatos.sort(key=lambda c: (not c.viable, -c.puntaje, c.distancia_km, c.receptor.id))
        return candidatos

    def _componentes(
        self, d: Donacion, r: Receptor, c: Candidato, vida_restante_h: float, ahora: datetime
    ) -> dict[str, float]:
        # necesidad: fracción de los kg donados que el receptor necesita, ponderada por su prioridad (1-3)
        puntos, cubiertas = 0.0, set()
        for it in d.items:
            nivel = r.necesidades.get(it["categoria"], 0)
            if nivel:
                cubiertas.add(it["categoria"])
            puntos += (it["kg"] or 0.0) * nivel / 3.0
        c.categorias_cubiertas = sorted(cubiertas)
        necesidad = puntos / d.total_kg if d.total_kg else 0.0

        cercania = max(0.0, 1.0 - c.distancia_km / DISTANCIA_MAX_KM)

        margen_h = (d.caduca_en - c.llegada).total_seconds() / 3600.0
        caducidad = max(0.0, min(1.0, (margen_h / vida_restante_h) / FRACCION_VIDA_IDEAL))

        capacidad = (
            max(0.0, min(1.0, c.kg_disponibles / (HOLGURA_CAPACIDAD * d.total_kg))) if d.total_kg else 0.0
        )

        base_semanal = 7.0 * max(r.capacidad_diaria_kg, 1.0)
        equidad = 1.0 - min(1.0, self._recibido_7_dias(r, ahora) / base_semanal)

        return {"necesidad": necesidad, "cercania": cercania, "caducidad": caducidad,
                "capacidad": capacidad, "equidad": equidad}

    # ------------------------------------------------------------------ ciclo de la oferta
    def ofrecer(self, donacion: Donacion) -> Oferta | None:
        """Ofrece la donación al mejor receptor viable que aún no la haya rechazado/omitido.

        Si no queda ninguno, la donación pasa a ``SIN_RECEPTOR`` (requiere atención del administrador).
        """
        ahora = reloj.ahora()
        # Se consulta la base (no la colección ``donacion.ofertas``, que puede estar desactualizada).
        previas = list(self.db.scalars(
            select(Oferta).where(
                Oferta.donacion_id == donacion.id,
                Oferta.estado.in_((EstadoOferta.RECHAZADA, EstadoOferta.EXPIRADA)),
            )
        ))
        excluir = {o.receptor_id for o in previas}
        candidatos = self.evaluar_receptores(donacion, excluir)
        donacion.evaluacion = {
            "evaluado_en": a_iso(ahora), "ronda": len(previas) + 1,
            "candidatos": [c.a_dict() for c in candidatos],
        }
        viables = [c for c in candidatos if c.viable]
        if not viables:
            donacion.estado = EstadoDonacion.SIN_RECEPTOR
            motivos = {c.receptor.nombre: c.motivos_exclusion for c in candidatos}
            registrar_evento(
                self.db, self.nombre, "sin_receptor",
                "Ningún receptor es viable para esta donación; queda en espera de atención del administrador.",
                donacion_id=donacion.id, detalle={"descartados": motivos},
            )
            notificar_donante(
                self.db, donacion, self.nombre,
                "Por ahora no encontré un receptor que pueda recibir tu donación a tiempo. "
                "Un administrador la revisará; te aviso en cuanto haya novedades.",
            )
            return None

        mejor = viables[0]
        oferta = Oferta(
            donacion_id=donacion.id, receptor_id=mejor.receptor.id, estado=EstadoOferta.PENDIENTE,
            puntaje=round(mejor.puntaje, 1), desglose={k: round(v, 2) for k, v in mejor.componentes.items()},
            justificacion=self._justificar(mejor, donacion, len(viables), ahora),
            creada_en=ahora, vence_en=ahora + timedelta(minutes=self.ajustes.vigencia_oferta_min),
        )
        self.db.add(oferta)
        donacion.estado = EstadoDonacion.OFRECIDA
        if donacion.primera_oferta_en is None:
            donacion.primera_oferta_en = ahora
        self.db.flush()
        registrar_evento(
            self.db, self.nombre, "oferta_creada" if not previas else "oferta_reasignada",
            f"Ofrecí la donación a {mejor.receptor.nombre} (puntaje {mejor.puntaje:.0f}/100). {oferta.justificacion}",
            donacion_id=donacion.id,
            detalle={"oferta_id": oferta.id, "receptor_id": mejor.receptor.id,
                     "desglose": oferta.desglose, "vence_en": a_iso(oferta.vence_en)},
        )
        return oferta

    def _justificar(self, c: Candidato, d: Donacion, n_viables: int, ahora: datetime) -> str:
        partes = [f"Mejor de {n_viables} receptor{'es' if n_viables != 1 else ''} viable{'s' if n_viables != 1 else ''}"]
        if c.categorias_cubiertas:
            nombres = ", ".join(CATEGORIAS[x].lower() for x in c.categorias_cubiertas)
            partes.append(f"necesita {nombres}")
        partes.append(f"está a {c.distancia_km:.1f} km (llegada {fmt_momento(c.llegada, ahora)})")
        partes.append(f"le quedan {fmt_kg(max(c.kg_disponibles, 0))} de capacidad hoy")
        return "; ".join(partes) + "."

    def responder(self, oferta: Oferta, aceptar: bool, motivo: str | None = None) -> Oferta:
        """Registra la respuesta del receptor. Si acepta, la donación queda ``ASIGNADA``.

        Si rechaza, solo se marca la oferta; el orquestador decide reasignar.
        """
        ahora = reloj.ahora()
        if oferta.estado != EstadoOferta.PENDIENTE:
            raise ValueError(f"La oferta {oferta.id} ya no está pendiente ({oferta.estado})")
        donacion = oferta.donacion
        oferta.respondida_en = ahora
        if aceptar:
            oferta.estado = EstadoOferta.ACEPTADA
            donacion.estado = EstadoDonacion.ASIGNADA
            donacion.receptor_id = oferta.receptor_id
            donacion.receptor = oferta.receptor  # mantiene la relación al día para el Logístico
            donacion.asignada_en = ahora
            registrar_evento(
                self.db, Agente.COORDINADOR, "oferta_aceptada",
                f"{oferta.receptor.nombre} aceptó la donación.", donacion_id=donacion.id,
                detalle={"oferta_id": oferta.id},
            )
        else:
            oferta.estado = EstadoOferta.RECHAZADA
            oferta.motivo = motivo or "Sin motivo indicado"
            registrar_evento(
                self.db, Agente.COORDINADOR, "oferta_rechazada",
                f"{oferta.receptor.nombre} rechazó la donación: {oferta.motivo}.", donacion_id=donacion.id,
                detalle={"oferta_id": oferta.id, "motivo": oferta.motivo},
            )
        return oferta

    def expirar_vencidas(self) -> list[Oferta]:
        """Marca como expiradas las ofertas pendientes cuyo tiempo límite ya pasó."""
        ahora = reloj.ahora()
        vencidas = list(self.db.scalars(
            select(Oferta).where(Oferta.estado == EstadoOferta.PENDIENTE, Oferta.vence_en <= ahora)
        ))
        for oferta in vencidas:
            oferta.estado = EstadoOferta.EXPIRADA
            oferta.respondida_en = ahora
            oferta.motivo = "No respondió a tiempo"
            registrar_evento(
                self.db, self.nombre, "oferta_expirada",
                f"{oferta.receptor.nombre} no respondió en {self.ajustes.vigencia_oferta_min} min; "
                "reasigno la donación.", donacion_id=oferta.donacion_id,
                detalle={"oferta_id": oferta.id},
            )
        return vencidas
