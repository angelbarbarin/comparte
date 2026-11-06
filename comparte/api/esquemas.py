"""Cuerpos de las peticiones de la API y serialización de las entidades a JSON.

Las respuestas se arman como diccionarios (no hay un modelo Pydantic por cada una) para mantener el MVP
pequeño; el contrato real son estos serializadores y las pruebas de ``tests/test_api.py``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..modelos import (
    Conversacion,
    Donacion,
    Donante,
    EstadoRecoleccion,
    EventoAgente,
    Mensaje,
    Oferta,
    Receptor,
    Recoleccion,
    Voluntario,
)

# ----------------------------------------------------------------------------- cuerpos de peticiones


class ConversacionIn(BaseModel):
    donante_id: int


class MensajeIn(BaseModel):
    texto: str = Field(min_length=1, max_length=2000)
    imagen_base64: str | None = None  # la foto va en base64 dentro del JSON (máx. 5 MB ya decodificada)
    imagen_tipo: Literal["image/jpeg", "image/png", "image/webp", "image/gif"] | None = None


class RespuestaIn(BaseModel):
    aceptar: bool
    motivo: str | None = Field(default=None, max_length=200)


class AvanceIn(BaseModel):
    estado: Literal["recogida", "entregada"]


class RevisionIn(BaseModel):
    aprobar: bool
    nota: str | None = Field(default=None, max_length=300)


class ConfirmacionIn(BaseModel):
    kg_recibidos: float | None = Field(default=None, gt=0, le=100000)


class ReceptorIn(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    tipo: Literal["banco_alimentos", "comedor", "albergue", "casa_hogar"] = "comedor"
    direccion: str = Field(default="", max_length=200)
    municipio: str = Field(min_length=2, max_length=60)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    horario_apertura: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    horario_cierre: str = Field(default="20:00", pattern=r"^\d{2}:\d{2}$")
    personas_atendidas: int = Field(default=0, ge=0)
    necesidades: dict[str, int] = Field(default_factory=dict)  # categoría -> prioridad 1-3
    capacidad_diaria_kg: float = Field(default=0, ge=0)
    capacidad_frio_kg: float = Field(default=0, ge=0)
    contacto: str = Field(default="", max_length=80)
    telefono: str = Field(default="", max_length=30)


class VerificacionIn(BaseModel):
    verificado: bool = True


class AvanceRelojIn(BaseModel):
    minutos: float = Field(gt=0, le=1440)


class FijarHoraIn(BaseModel):
    hora: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ReinicioIn(BaseModel):
    con_historial: bool = True


# ------------------------------------------------------------------------------------ serialización


def iso(momento: datetime | None) -> str | None:
    return momento.isoformat(timespec="seconds") if momento else None


def url_foto(ruta: str | None) -> str | None:
    """'uploads/conv1_x.png' -> '/uploads/conv1_x.png' (la ruta pública que sirve la API)."""
    return f"/uploads/{Path(ruta).name}" if ruta else None


class Serializador:
    def __init__(self, db: Session):
        self.db = db

    def donante(self, d: Donante) -> dict:
        return {"id": d.id, "nombre": d.nombre, "giro": d.giro, "direccion": d.direccion,
                "municipio": d.municipio, "lat": d.lat, "lon": d.lon, "contacto": d.contacto}

    def receptor(self, r: Receptor) -> dict:
        return {"id": r.id, "nombre": r.nombre, "tipo": r.tipo, "direccion": r.direccion,
                "municipio": r.municipio, "lat": r.lat, "lon": r.lon,
                "horario_apertura": r.horario_apertura, "horario_cierre": r.horario_cierre,
                "personas_atendidas": r.personas_atendidas, "necesidades": r.necesidades,
                "capacidad_diaria_kg": r.capacidad_diaria_kg, "capacidad_frio_kg": r.capacidad_frio_kg,
                "verificado": r.verificado, "contacto": r.contacto}

    def voluntario(self, v: Voluntario) -> dict:
        return {"id": v.id, "nombre": v.nombre, "vehiculo": v.vehiculo, "capacidad_kg": v.capacidad_kg,
                "tiene_hielera": v.tiene_hielera, "municipio": v.municipio, "lat": v.lat, "lon": v.lon,
                "disponible": v.disponible, "disponible_desde": v.disponible_desde,
                "disponible_hasta": v.disponible_hasta}

    def mensaje(self, m: Mensaje) -> dict:
        return {"id": m.id, "rol": m.rol, "texto": m.texto, "imagen": url_foto(m.imagen), "creado_en": iso(m.creado_en)}

    def conversacion(self, c: Conversacion) -> dict:
        mensajes = self.db.scalars(select(Mensaje).where(Mensaje.conversacion_id == c.id).order_by(Mensaje.id))
        return {"id": c.id, "donante": self.donante(c.donante), "canal": c.canal, "donacion_id": c.donacion_id,
                "mensajes": [self.mensaje(m) for m in mensajes]}

    def evento(self, e: EventoAgente) -> dict:
        return {"id": e.id, "donacion_id": e.donacion_id, "agente": e.agente, "accion": e.accion,
                "resumen": e.resumen, "detalle": e.detalle, "creado_en": iso(e.creado_en)}

    def _resumen_donacion(self, d: Donacion) -> dict:
        return {"id": d.id, "estado": d.estado, "total_kg": d.total_kg, "categoria_principal": d.categoria_principal,
                "items": d.items, "donante": {"id": d.donante.id, "nombre": d.donante.nombre, "municipio": d.donante.municipio},
                "caduca_en": iso(d.caduca_en)}

    def oferta(self, o: Oferta, con_donacion: bool = True) -> dict:
        datos = {"id": o.id, "donacion_id": o.donacion_id, "estado": o.estado,
                 "receptor": {"id": o.receptor.id, "nombre": o.receptor.nombre},
                 "puntaje": o.puntaje, "desglose": o.desglose, "justificacion": o.justificacion,
                 "creada_en": iso(o.creada_en), "vence_en": iso(o.vence_en),
                 "respondida_en": iso(o.respondida_en), "motivo": o.motivo}
        if con_donacion:
            datos["donacion"] = self._resumen_donacion(o.donacion)
        return datos

    def recoleccion(self, r: Recoleccion, con_donacion: bool = True) -> dict:
        datos = {"id": r.id, "donacion_id": r.donacion_id, "estado": r.estado,
                 "voluntario": {"id": r.voluntario.id, "nombre": r.voluntario.nombre, "vehiculo": r.voluntario.vehiculo},
                 "ruta": r.ruta, "recoger_estimado": iso(r.recoger_estimado), "entrega_estimada": iso(r.entrega_estimada),
                 "justificacion": r.justificacion, "creada_en": iso(r.creada_en), "vence_en": iso(r.vence_en),
                 "respondida_en": iso(r.respondida_en), "motivo": r.motivo}
        if con_donacion:
            d = r.donacion
            datos["donacion"] = {**self._resumen_donacion(d),
                                 "receptor": {"id": d.receptor.id, "nombre": d.receptor.nombre} if d.receptor else None,
                                 "donante_direccion": d.donante.direccion,
                                 "receptor_direccion": d.receptor.direccion if d.receptor else None,
                                 "requiere_frio": d.requiere_frio}
        return datos

    def donacion(self, d: Donacion, detalle: bool = False) -> dict:
        datos = {
            "id": d.id, "estado": d.estado, "total_kg": d.total_kg, "categoria_principal": d.categoria_principal,
            "items": d.items, "requiere_frio": d.requiere_frio, "simulada": d.simulada,
            "donante": {"id": d.donante.id, "nombre": d.donante.nombre, "municipio": d.donante.municipio,
                        "lat": d.donante.lat, "lon": d.donante.lon},
            "receptor": ({"id": d.receptor.id, "nombre": d.receptor.nombre, "municipio": d.receptor.municipio,
                          "lat": d.receptor.lat, "lon": d.receptor.lon} if d.receptor else None),
            "caduca_en": iso(d.caduca_en), "caducidad_estimada": d.caducidad_estimada,
            "creada_en": iso(d.creada_en), "completada_en": iso(d.completada_en),
            "inocuidad": {"nivel": (d.inocuidad or {}).get("nivel"),
                          "requiere_revision": (d.inocuidad or {}).get("requiere_revision", False)},
            "foto": url_foto(d.foto),
        }
        if not detalle:
            return datos

        ofertas = self.db.scalars(select(Oferta).where(Oferta.donacion_id == d.id).order_by(Oferta.id))
        recolecciones = list(self.db.scalars(
            select(Recoleccion).where(Recoleccion.donacion_id == d.id).order_by(Recoleccion.id)))
        activa = next((r for r in reversed(recolecciones)
                       if r.estado not in (EstadoRecoleccion.RECHAZADA, EstadoRecoleccion.EXPIRADA, EstadoRecoleccion.CANCELADA)), None)
        eventos = self.db.scalars(select(EventoAgente).where(EventoAgente.donacion_id == d.id).order_by(EventoAgente.id))
        datos.update(
            inocuidad=d.inocuidad, condiciones=d.condiciones, kg_recibidos=d.kg_recibidos,
            recoleccion_desde=iso(d.recoleccion_desde), recoleccion_hasta=iso(d.recoleccion_hasta),
            asignada_en=iso(d.asignada_en), entregada_en=iso(d.entregada_en),
            segundos_registro=d.segundos_registro,
            evaluacion=d.evaluacion,
            ofertas=[self.oferta(o, con_donacion=False) for o in ofertas],
            recolecciones=[self.recoleccion(r, con_donacion=False) for r in recolecciones],
            recoleccion_activa=self.recoleccion(activa, con_donacion=False) if activa else None,
            eventos=[self.evento(e) for e in eventos],
        )
        return datos
