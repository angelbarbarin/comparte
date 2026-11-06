"""Rutas REST de ComParte (prefijo ``/api``). La documentación interactiva queda en ``/docs``.

Convenciones: entidades inexistentes -> 404; transiciones inválidas (p. ej. responder dos veces una
oferta) -> 409; datos mal formados -> 422. Las consultas llaman a ``orquestador.tick()`` para aplicar los
vencimientos pendientes (ofertas sin respuesta, donaciones caducadas) antes de responder.

⚠️  MVP sin autenticación: cualquiera puede "actuar como" cualquier donante, receptor, voluntario o
administrador. Ver docs/ALCANCE_MVP.md (limitaciones).

Nota técnica: este módulo NO usa ``from __future__ import annotations`` a propósito. FastAPI necesita
resolver en tiempo de ejecución las anotaciones ``DB`` y ``ORQ`` (definidas dentro de
``construir_router``); con anotaciones diferidas las trataría como parámetros de consulta.
"""

import base64
import binascii
from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session, sessionmaker

from .. import __version__, reloj
from ..config import Ajustes
from ..datos_demo import reiniciar_demo
from ..db import sesion_por_peticion
from ..llm import Extractor
from ..llm.base import Imagen
from ..modelos import (
    Conversacion,
    Donacion,
    Donante,
    EstadoDonacion,
    EstadoOferta,
    EstadoRecoleccion,
    EventoAgente,
    Oferta,
    Receptor,
    Recoleccion,
    Voluntario,
)
from ..orquestador import Orquestador
from .esquemas import (
    AvanceIn,
    AvanceRelojIn,
    ConfirmacionIn,
    ConversacionIn,
    FijarHoraIn,
    MensajeIn,
    ReceptorIn,
    ReinicioIn,
    RespuestaIn,
    RevisionIn,
    Serializador,
    VerificacionIn,
)

MAX_BYTES_IMAGEN = 5 * 1024 * 1024


@dataclass
class Contexto:
    ajustes: Ajustes
    motor: Engine
    fabrica: sessionmaker[Session]
    extractor: Extractor


def _decodificar_imagen(cuerpo: MensajeIn) -> Imagen | None:
    if not cuerpo.imagen_base64:
        return None
    if not cuerpo.imagen_tipo:
        raise HTTPException(400, "Falta imagen_tipo (image/jpeg, image/png, image/webp o image/gif)")
    try:
        datos = base64.b64decode(cuerpo.imagen_base64, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(400, "imagen_base64 no es base64 válido") from None
    if len(datos) > MAX_BYTES_IMAGEN:
        raise HTTPException(413, "La imagen pesa más de 5 MB")
    return datos, cuerpo.imagen_tipo


def construir_router(ctx: Contexto) -> APIRouter:
    router = APIRouter(prefix="/api")
    obtener_db = sesion_por_peticion(ctx.fabrica)

    def obtener_orq(db: Annotated[Session, Depends(obtener_db)]) -> Orquestador:
        return Orquestador(db, extractor=ctx.extractor, ajustes=ctx.ajustes)

    DB = Annotated[Session, Depends(obtener_db)]
    ORQ = Annotated[Orquestador, Depends(obtener_orq)]

    def ser(db: Session) -> Serializador:
        return Serializador(db)

    def existente(db: Session, modelo, id_: int):
        entidad = db.get(modelo, id_)
        if entidad is None:
            raise HTTPException(404, f"No existe {modelo.__name__} con id {id_}")
        return entidad

    # ------------------------------------------------------------------ estado general
    @router.get("/estado", tags=["general"])
    def estado():
        return {
            "version": __version__, "motor_lenguaje": ctx.extractor.nombre,
            "hora": reloj.ahora().isoformat(timespec="seconds"), "reloj_de_demo": reloj.hay_desfase(),
            "vigencia_oferta_min": ctx.ajustes.vigencia_oferta_min,
            "vigencia_recoleccion_min": ctx.ajustes.vigencia_recoleccion_min,
        }

    # ------------------------------------------------------------------ catálogos de actores
    @router.get("/donantes", tags=["actores"])
    def donantes(db: DB):
        return [ser(db).donante(d) for d in db.scalars(select(Donante).order_by(Donante.id))]

    @router.get("/receptores", tags=["actores"])
    def receptores(db: DB):
        return [ser(db).receptor(r) for r in db.scalars(select(Receptor).order_by(Receptor.id))]

    @router.post("/receptores", status_code=201, tags=["actores"])
    def crear_receptor(cuerpo: ReceptorIn, orq: ORQ, db: DB):
        """Alta de un receptor (CP-03). Nace sin verificar: no recibe ofertas hasta que un administrador lo valide."""
        return ser(db).receptor(orq.registrar_receptor(**cuerpo.model_dump()))

    @router.post("/receptores/{receptor_id}/verificacion", tags=["actores"])
    def verificar_receptor(receptor_id: int, cuerpo: VerificacionIn, orq: ORQ, db: DB):
        return ser(db).receptor(orq.verificar_receptor(receptor_id, cuerpo.verificado))

    @router.get("/voluntarios", tags=["actores"])
    def voluntarios(db: DB):
        return [ser(db).voluntario(v) for v in db.scalars(select(Voluntario).order_by(Voluntario.id))]

    # ------------------------------------------------------------------ conversación con el Captador
    @router.post("/conversaciones", status_code=201, tags=["captador"])
    def iniciar_conversacion(cuerpo: ConversacionIn, orq: ORQ, db: DB):
        return ser(db).conversacion(orq.iniciar_conversacion(cuerpo.donante_id))

    @router.get("/conversaciones/{conversacion_id}", tags=["captador"])
    def ver_conversacion(conversacion_id: int, orq: ORQ, db: DB):
        orq.tick()
        return ser(db).conversacion(existente(db, Conversacion, conversacion_id))

    @router.post("/conversaciones/{conversacion_id}/mensajes", tags=["captador"])
    def enviar_mensaje(conversacion_id: int, cuerpo: MensajeIn, orq: ORQ, db: DB):
        """Mensaje del donante (con foto opcional). Si queda registrada una donación, el orquestador la enruta."""
        resultado = orq.mensaje_donante(conversacion_id, cuerpo.texto, _decodificar_imagen(cuerpo))
        s = ser(db)
        return {
            "conversacion": s.conversacion(db.get(Conversacion, conversacion_id)),
            "donacion": s.donacion(resultado.donacion) if resultado.donacion else None,
            "bloqueada": resultado.bloqueada,
        }

    # ------------------------------------------------------------------ donaciones
    @router.get("/donaciones", tags=["donaciones"])
    def listar_donaciones(
        orq: ORQ, db: DB, estado: str | None = None, donante_id: int | None = None,
        receptor_id: int | None = None, simuladas: bool = False, limite: Annotated[int, Query(ge=1, le=500)] = 100,
    ):
        orq.tick()
        consulta = select(Donacion).order_by(Donacion.id.desc()).limit(limite)
        if not simuladas:
            consulta = consulta.where(Donacion.simulada.is_(False))
        if estado:
            consulta = consulta.where(Donacion.estado == estado)
        if donante_id is not None:
            consulta = consulta.where(Donacion.donante_id == donante_id)
        if receptor_id is not None:
            consulta = consulta.where(Donacion.receptor_id == receptor_id)
        return [ser(db).donacion(d) for d in db.scalars(consulta)]

    @router.get("/donaciones/{donacion_id}", tags=["donaciones"])
    def ver_donacion(donacion_id: int, orq: ORQ, db: DB):
        orq.tick()
        return ser(db).donacion(existente(db, Donacion, donacion_id), detalle=True)

    @router.post("/donaciones/{donacion_id}/revision", tags=["admin"])
    def revisar_donacion(donacion_id: int, cuerpo: RevisionIn, orq: ORQ, db: DB):
        """Decisión humana sobre una donación con alimentos de riesgo."""
        return ser(db).donacion(orq.revision_humana(donacion_id, cuerpo.aprobar, cuerpo.nota), detalle=True)

    @router.post("/donaciones/{donacion_id}/reintento", tags=["admin"])
    def reintentar_donacion(donacion_id: int, orq: ORQ, db: DB):
        return ser(db).donacion(orq.reintentar(donacion_id), detalle=True)

    @router.post("/donaciones/{donacion_id}/confirmacion-recepcion", tags=["receptor"])
    def confirmar_recepcion(donacion_id: int, cuerpo: ConfirmacionIn, orq: ORQ, db: DB):
        return ser(db).donacion(orq.confirmar_recepcion(donacion_id, cuerpo.kg_recibidos), detalle=True)

    # ------------------------------------------------------------------ receptores y ofertas
    @router.post("/ofertas/{oferta_id}/respuesta", tags=["receptor"])
    def responder_oferta(oferta_id: int, cuerpo: RespuestaIn, orq: ORQ, db: DB):
        return ser(db).oferta(orq.responder_oferta(oferta_id, cuerpo.aceptar, cuerpo.motivo))

    @router.get("/receptores/{receptor_id}/tareas", tags=["receptor"])
    def tareas_receptor(receptor_id: int, orq: ORQ, db: DB):
        orq.tick()
        existente(db, Receptor, receptor_id)
        s = ser(db)
        ofertas = db.scalars(select(Oferta).where(
            Oferta.receptor_id == receptor_id, Oferta.estado == EstadoOferta.PENDIENTE).order_by(Oferta.id))

        def donaciones(*estados):
            return [s.donacion(d) for d in db.scalars(select(Donacion).where(
                Donacion.receptor_id == receptor_id, Donacion.estado.in_(estados)).order_by(Donacion.id.desc()))]

        return {
            "ofertas": [s.oferta(o) for o in ofertas],
            "en_camino": donaciones(EstadoDonacion.ASIGNADA, EstadoDonacion.EN_RECOLECCION, EstadoDonacion.EN_CAMINO),
            "por_confirmar": donaciones(EstadoDonacion.ENTREGADA),
            "completadas": [d for d in donaciones(EstadoDonacion.COMPLETADA) if not d["simulada"]][:5],
        }

    # ------------------------------------------------------------------ voluntarios y recolecciones
    @router.post("/recolecciones/{recoleccion_id}/respuesta", tags=["voluntario"])
    def responder_recoleccion(recoleccion_id: int, cuerpo: RespuestaIn, orq: ORQ, db: DB):
        return ser(db).recoleccion(orq.responder_recoleccion(recoleccion_id, cuerpo.aceptar, cuerpo.motivo))

    @router.post("/recolecciones/{recoleccion_id}/avance", tags=["voluntario"])
    def avanzar_recoleccion(recoleccion_id: int, cuerpo: AvanceIn, orq: ORQ, db: DB):
        return ser(db).recoleccion(orq.avanzar_recoleccion(recoleccion_id, cuerpo.estado))

    @router.get("/voluntarios/{voluntario_id}/tareas", tags=["voluntario"])
    def tareas_voluntario(voluntario_id: int, orq: ORQ, db: DB):
        orq.tick()
        existente(db, Voluntario, voluntario_id)
        s = ser(db)

        def recolecciones(*estados, limite=50):
            return [s.recoleccion(r) for r in db.scalars(select(Recoleccion).where(
                Recoleccion.voluntario_id == voluntario_id, Recoleccion.estado.in_(estados))
                .order_by(Recoleccion.id.desc()).limit(limite))]

        return {
            "propuestas": recolecciones(EstadoRecoleccion.PROPUESTA),
            "activas": recolecciones(EstadoRecoleccion.ACEPTADA, EstadoRecoleccion.RECOGIDA),
            "entregadas": recolecciones(EstadoRecoleccion.ENTREGADA, limite=5),
        }

    # ------------------------------------------------------------------ administración
    @router.get("/admin/pendientes", tags=["admin"])
    def pendientes(orq: ORQ, db: DB):
        """Lo que requiere a una persona: validar alimentos de riesgo, atender donaciones atoradas y verificar receptores."""
        orq.tick()
        s = ser(db)

        def por_estado(*estados):
            return db.scalars(select(Donacion).where(Donacion.estado.in_(estados)).order_by(Donacion.id))

        return {
            "validacion": [{**s.donacion(d), "inocuidad": d.inocuidad, "condiciones": d.condiciones}
                           for d in por_estado(EstadoDonacion.PENDIENTE_VALIDACION)],
            "atoradas": [s.donacion(d) for d in por_estado(EstadoDonacion.SIN_RECEPTOR, EstadoDonacion.SIN_VOLUNTARIO)],
            "receptores_sin_verificar": [s.receptor(r) for r in db.scalars(
                select(Receptor).where(Receptor.verificado.is_(False)).order_by(Receptor.id))],
        }

    @router.get("/eventos", tags=["admin"])
    def eventos(db: DB, limite: Annotated[int, Query(ge=1, le=500)] = 100, donacion_id: int | None = None):
        """Bitácora de auditoría de decisiones de agentes (más recientes primero)."""
        consulta = select(EventoAgente).order_by(EventoAgente.id.desc()).limit(limite)
        if donacion_id is not None:
            consulta = consulta.where(EventoAgente.donacion_id == donacion_id)
        return [ser(db).evento(e) for e in db.scalars(consulta)]

    # ------------------------------------------------------------------ impacto
    @router.get("/impacto", tags=["impacto"])
    def impacto(orq: ORQ, donante_id: int | None = None, receptor_id: int | None = None,
                simuladas: bool = True, dias: Annotated[int, Query(ge=1, le=365)] = 30):
        orq.tick()
        return orq.impacto.resumen(donante_id=donante_id, receptor_id=receptor_id, dias=dias,
                                   incluir_simuladas=simuladas)

    @router.get("/impacto/donantes/{donante_id}", tags=["impacto"])
    def reporte_donante(donante_id: int, orq: ORQ):
        """Reporte de impacto de un donante (CP-08, parcial: sin PDF ni envío mensual programado)."""
        try:
            return orq.impacto.reporte_donante(donante_id)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from None

    # ------------------------------------------------------------------ controles de la demostración
    @router.post("/demo/reiniciar", tags=["demo"])
    def reiniciar(cuerpo: ReinicioIn):
        """Borra todos los datos, recarga el piloto simulado y vuelve a fijar la hora de demo."""
        return reiniciar_demo(ctx.motor, ctx.fabrica, ctx.ajustes.hora_demo, cuerpo.con_historial)

    @router.post("/demo/avanzar-reloj", tags=["demo"])
    def avanzar_reloj(cuerpo: AvanceRelojIn, orq: ORQ):
        """Adelanta el reloj de la aplicación para demostrar vencimientos de ofertas y caducidades."""
        reloj.avanzar(cuerpo.minutos)
        orq.tick()
        return {"hora": reloj.ahora().isoformat(timespec="seconds")}

    @router.post("/demo/fijar-hora", tags=["demo"])
    def fijar_hora(cuerpo: FijarHoraIn):
        """Fija la hora de la aplicación a las HH:MM de hoy (el tiempo sigue corriendo desde ahí)."""
        return {"hora": reloj.fijar_hora_hoy(cuerpo.hora).isoformat(timespec="seconds")}

    return router
