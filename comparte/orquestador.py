"""Orquestador: el único componente que conoce a los cuatro agentes y decide quién actúa después.

Los agentes no se llaman entre sí: cada uno hace su trabajo y devuelve el control. El orquestador
**enruta** según el estado de la donación y deja constancia de cada traspaso en la bitácora (esos
eventos aparecen en la línea de tiempo de la interfaz como "Orquestador"). Así cada agente es
modular y se puede probar y desplegar por separado (rango de calidad de mantenibilidad).

    Donante ─chat→ Captador ──registra──▶ Orquestador
        riesgo alto ─▶ revisión humana ─aprueba─┐
        riesgo bajo ───────────────────────────┴▶ Coordinador ─oferta─▶ Receptor
                      rechaza / no responde ◀─ reasigna ─┘          │ acepta
                                                                    ▼
                    Impacto ◀─confirma recepción─ Receptor ◀─entrega─ Logístico ─▶ Voluntario

Todos los métodos públicos hacen ``commit`` al terminar. Las entidades que no existen lanzan
``LookupError`` y las transiciones inválidas ``ValueError`` (la API las traduce a 404 y 409).

Los tiempos límite (ofertas, propuestas, caducidad) se evalúan en ``tick()``, que la API llama al
consultar datos; no hay un planificador en segundo plano en el MVP.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import reloj
from .agentes.base import notificar_donante, registrar_evento
from .agentes.captador import AgenteCaptador, ResultadoCaptador
from .agentes.coordinador import AgenteCoordinador
from .agentes.impacto import AgenteImpacto
from .agentes.logistico import AgenteLogistico
from .config import Ajustes, obtener_ajustes
from .llm import Extractor, crear_extractor
from .llm.base import Imagen
from .modelos import (
    Agente,
    Conversacion,
    Donacion,
    Donante,
    EstadoDonacion,
    EstadoOferta,
    EstadoRecoleccion,
    Oferta,
    Receptor,
    Recoleccion,
)


class Orquestador:
    nombre = Agente.ORQUESTADOR

    def __init__(self, db: Session, extractor: Extractor | None = None, ajustes: Ajustes | None = None):
        self.db = db
        self.ajustes = ajustes or obtener_ajustes()
        self.captador = AgenteCaptador(db, extractor or crear_extractor(self.ajustes), self.ajustes.carpeta_datos)
        self.coordinador = AgenteCoordinador(db, self.ajustes)
        self.logistico = AgenteLogistico(db, self.ajustes)
        self.impacto = AgenteImpacto(db)

    # ------------------------------------------------------------------ utilidades
    def _obtener(self, modelo, id_: int):
        entidad = self.db.get(modelo, id_)
        if entidad is None:
            raise LookupError(f"No existe {modelo.__name__} con id {id_}")
        return entidad

    def _evento(self, accion: str, resumen: str, donacion: Donacion | None = None, **detalle) -> None:
        registrar_evento(self.db, self.nombre, accion, resumen,
                         donacion_id=donacion.id if donacion else None, detalle=detalle)

    # ------------------------------------------------------------------ 1. captura
    def iniciar_conversacion(self, donante_id: int) -> Conversacion:
        donante = self._obtener(Donante, donante_id)
        conversacion = self.captador.iniciar_conversacion(donante)
        self.db.commit()
        return conversacion

    def mensaje_donante(
        self, conversacion_id: int, texto: str, imagen: Imagen | None = None
    ) -> ResultadoCaptador:
        """Un mensaje del donante. Si el Captador registra una donación, se enruta de inmediato."""
        conversacion = self._obtener(Conversacion, conversacion_id)
        resultado = self.captador.procesar_mensaje(conversacion, texto, imagen)
        if resultado.donacion is not None:
            self._enrutar(resultado.donacion)
        self.db.commit()
        return resultado

    def _enrutar(self, d: Donacion) -> None:
        ev = d.inocuidad or {}
        if ev.get("requiere_revision"):
            d.estado = EstadoDonacion.PENDIENTE_VALIDACION
            self._evento(
                "enrutada_a_revision",
                f"Donación #{d.id} con riesgo {ev.get('nivel', 'alto')}: la envío a revisión humana antes de asignarla.",
                d, motivos=ev.get("motivos", []),
            )
            notificar_donante(
                self.db, d, self.nombre,
                "Tu donación incluye alimentos que requieren la revisión de una persona del equipo antes de "
                "asignarse. Te aviso en cuanto la valide.",
            )
        else:
            self._evento("enrutada_a_coordinador",
                         f"Donación #{d.id} sin riesgo que exija revisión: la turno al Agente Coordinador.", d)
            self._ofrecer(d)

    # ------------------------------------------------------------------ 2. revisión humana
    def revision_humana(self, donacion_id: int, aprobar: bool, nota: str | None = None) -> Donacion:
        """Decisión de una persona sobre una donación con alimentos de riesgo (CP-02 / CP-09)."""
        d = self._obtener(Donacion, donacion_id)
        if d.estado != EstadoDonacion.PENDIENTE_VALIDACION:
            raise ValueError(f"La donación #{d.id} no está pendiente de validación ({d.estado})")
        sufijo = f" Nota: {nota}" if nota else ""
        if aprobar:
            ahora = reloj.ahora()
            # La revisión pudo tardar: se reabre la ventana de recolección desde este momento.
            d.recoleccion_desde = max(d.recoleccion_desde, ahora)
            d.recoleccion_hasta = max(d.recoleccion_hasta, min(d.recoleccion_desde + timedelta(hours=2), d.caduca_en))
            if d.recoleccion_hasta <= d.recoleccion_desde:
                d.recoleccion_hasta = d.recoleccion_desde + timedelta(minutes=30)
            registrar_evento(self.db, Agente.HUMANO, "revision_aprobada",
                             f"Una persona aprobó la donación #{d.id}.{sufijo}", donacion_id=d.id,
                             detalle={"nota": nota})
            notificar_donante(self.db, d, Agente.HUMANO, "Una persona del equipo revisó y aprobó tu donación.")
            self._ofrecer(d)
        else:
            d.estado = EstadoDonacion.RECHAZADA
            registrar_evento(self.db, Agente.HUMANO, "revision_rechazada",
                             f"Una persona rechazó la donación #{d.id}.{sufijo}", donacion_id=d.id,
                             detalle={"nota": nota})
            notificar_donante(self.db, d, Agente.HUMANO,
                              "Una persona del equipo revisó tu donación y no pudimos aceptarla."
                              + (f" Motivo: {nota}." if nota else "") + " Gracias por avisar.")
        self.db.commit()
        return d

    # ------------------------------------------------------------------ 3. asignación
    def _ofrecer(self, d: Donacion, reiniciar: bool = False, anterior: str | None = None) -> None:
        oferta = self.coordinador.ofrecer(d, reiniciar)
        if oferta is not None:
            prefijo = f"{anterior} no pudo recibirla. " if anterior else ""
            notificar_donante(
                self.db, d, Agente.COORDINADOR,
                f"{prefijo}Ofrecí tu donación a {oferta.receptor.nombre} ({oferta.puntaje:.0f}/100). "
                "Te aviso cuando responda.",
            )

    def responder_oferta(self, oferta_id: int, aceptar: bool, motivo: str | None = None) -> Oferta:
        """Respuesta de un receptor a una oferta."""
        oferta = self._obtener(Oferta, oferta_id)
        d = oferta.donacion
        if d.estado != EstadoDonacion.OFRECIDA:
            raise ValueError(f"La donación #{d.id} ya no está ofrecida ({d.estado})")
        self.coordinador.responder(oferta, aceptar, motivo)
        if aceptar:
            self._evento("enrutada_a_logistico",
                         f"{oferta.receptor.nombre} aceptó la donación #{d.id}: la turno al Agente Logístico.", d)
            notificar_donante(self.db, d, Agente.COORDINADOR,
                              f"{oferta.receptor.nombre} aceptó tu donación. Ahora busco quién la recoja.")
            self._proponer(d)
        else:
            self._evento("reasignacion",
                         f"{oferta.receptor.nombre} rechazó la donación #{d.id}: pido al Coordinador otro receptor.", d)
            self._ofrecer(d, anterior=oferta.receptor.nombre)
        self.db.commit()
        return oferta

    # ------------------------------------------------------------------ 4. logística
    def _proponer(self, d: Donacion, reiniciar: bool = False) -> None:
        self.logistico.proponer(d, reiniciar)

    def responder_recoleccion(self, recoleccion_id: int, aceptar: bool, motivo: str | None = None) -> Recoleccion:
        """Respuesta de un voluntario a una propuesta de recolección."""
        rec = self._obtener(Recoleccion, recoleccion_id)
        d = rec.donacion
        self.logistico.responder(rec, aceptar, motivo)
        if aceptar:
            self._evento("recoleccion_en_curso",
                         f"{rec.voluntario.nombre} va por la donación #{d.id}; sigo el avance hasta la entrega.", d)
        else:
            self._evento("reasignacion",
                         f"{rec.voluntario.nombre} rechazó la recolección de la donación #{d.id}: pido otro voluntario.", d)
            self._proponer(d)
        self.db.commit()
        return rec

    def avanzar_recoleccion(self, recoleccion_id: int, nuevo_estado: str) -> Recoleccion:
        """El voluntario avisa que ``recogida`` o ``entregada`` la donación."""
        if nuevo_estado not in (EstadoRecoleccion.RECOGIDA, EstadoRecoleccion.ENTREGADA):
            raise ValueError("El estado debe ser 'recogida' o 'entregada'")
        rec = self._obtener(Recoleccion, recoleccion_id)
        self.logistico.avanzar(rec, nuevo_estado)
        if nuevo_estado == EstadoRecoleccion.ENTREGADA:
            self._evento("espera_confirmacion",
                         f"Donación #{rec.donacion_id} entregada: espero la confirmación de {rec.donacion.receptor.nombre}.",
                         rec.donacion)
        self.db.commit()
        return rec

    # ------------------------------------------------------------------ 5. cierre e impacto
    def confirmar_recepcion(self, donacion_id: int, kg_recibidos: float | None = None) -> Donacion:
        """El receptor confirma que recibió la donación (opcionalmente con los kg reales)."""
        d = self._obtener(Donacion, donacion_id)
        if d.estado != EstadoDonacion.ENTREGADA:
            raise ValueError(f"La donación #{d.id} aún no ha sido entregada por el voluntario ({d.estado})")
        if kg_recibidos is not None:
            if kg_recibidos <= 0:
                raise ValueError("Los kg recibidos deben ser mayores que cero")
            d.kg_recibidos = round(kg_recibidos, 2)
        d.estado, d.completada_en = EstadoDonacion.COMPLETADA, reloj.ahora()
        self._evento("enrutada_a_impacto",
                     f"{d.receptor.nombre} confirmó la recepción de la donación #{d.id}: la turno al Agente de Impacto.", d)
        self.impacto.registrar(d)
        self.db.commit()
        return d

    # ------------------------------------------------------------------ 6. tiempo y excepciones
    def tick(self) -> None:
        """Aplica los vencimientos: ofertas y propuestas sin respuesta (reasigna) y donaciones caducadas."""
        for oferta in self.coordinador.expirar_vencidas():
            if oferta.donacion.estado == EstadoDonacion.OFRECIDA:
                self._evento("reasignacion",
                             f"{oferta.receptor.nombre} no respondió: pido al Coordinador otro receptor.", oferta.donacion)
                self._ofrecer(oferta.donacion, anterior=oferta.receptor.nombre)
        for rec in self.logistico.expirar_vencidas():
            if rec.donacion.estado == EstadoDonacion.ASIGNADA:
                self._evento("reasignacion",
                             f"{rec.voluntario.nombre} no respondió: pido al Logístico otro voluntario.", rec.donacion)
                self._proponer(rec.donacion)

        abiertas = EstadoDonacion.ACTIVAS - {EstadoDonacion.ENTREGADA}
        for d in self.db.scalars(
            select(Donacion).where(Donacion.estado.in_(abiertas), Donacion.caduca_en <= reloj.ahora())
        ):
            self._caducar(d)
        self.db.commit()

    def _caducar(self, d: Donacion) -> None:
        for o in self.db.scalars(select(Oferta).where(Oferta.donacion_id == d.id, Oferta.estado == EstadoOferta.PENDIENTE)):
            o.estado = EstadoOferta.CANCELADA
        for r in self.db.scalars(select(Recoleccion).where(
                Recoleccion.donacion_id == d.id,
                Recoleccion.estado.in_((EstadoRecoleccion.PROPUESTA, EstadoRecoleccion.ACEPTADA, EstadoRecoleccion.RECOGIDA)))):
            r.estado = EstadoRecoleccion.CANCELADA
        d.estado = EstadoDonacion.CADUCADA
        self._evento("donacion_caducada",
                     f"La donación #{d.id} caducó antes de completarse; cancelo ofertas y recolecciones pendientes.", d)
        notificar_donante(self.db, d, self.nombre,
                          "Lamentablemente tu donación caducó antes de poder entregarse. Gracias por intentarlo; "
                          "la próxima vez avísanos con más margen si puedes.")

    def reintentar(self, donacion_id: int) -> Donacion:
        """El administrador vuelve a buscar receptor o voluntario en una donación atorada."""
        d = self._obtener(Donacion, donacion_id)
        if d.estado == EstadoDonacion.SIN_RECEPTOR:
            registrar_evento(self.db, Agente.HUMANO, "reintento", f"Una persona pidió reintentar buscar receptor para la donación #{d.id}.", donacion_id=d.id)
            self._ofrecer(d, reiniciar=True)
        elif d.estado == EstadoDonacion.SIN_VOLUNTARIO:
            registrar_evento(self.db, Agente.HUMANO, "reintento", f"Una persona pidió reintentar buscar voluntario para la donación #{d.id}.", donacion_id=d.id)
            self._proponer(d, reiniciar=True)
        else:
            raise ValueError(f"La donación #{d.id} no está atorada ({d.estado})")
        self.db.commit()
        return d

    # ------------------------------------------------------------------ 7. organizaciones
    def registrar_receptor(self, **campos) -> Receptor:
        """Alta de un receptor (CP-03). Nace **sin verificar**: no recibe ofertas hasta que un
        administrador lo valide (supervisión humana de organizaciones nuevas, sección 4.1)."""
        receptor = Receptor(**{**campos, "verificado": False})
        self.db.add(receptor)
        self.db.flush()
        registrar_evento(self.db, self.nombre, "receptor_registrado",
                         f"Se registró el receptor «{receptor.nombre}»; queda pendiente de verificación.",
                         detalle={"receptor_id": receptor.id})
        self.db.commit()
        return receptor

    def verificar_receptor(self, receptor_id: int, verificado: bool = True) -> Receptor:
        receptor = self._obtener(Receptor, receptor_id)
        receptor.verificado = verificado
        registrar_evento(self.db, Agente.HUMANO, "receptor_verificado" if verificado else "receptor_desverificado",
                         f"Una persona {'verificó' if verificado else 'retiró la verificación de'} «{receptor.nombre}».",
                         detalle={"receptor_id": receptor.id})
        self.db.commit()
        return receptor
